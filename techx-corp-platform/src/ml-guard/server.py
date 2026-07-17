"""ml-guard — self-hosted grounding gate (TF1-61 / MANDATE-06, ADR-013).

Một model mDeBERTa-v3-base-mnli-xnli (MIT, XNLI có tiếng Việt) làm NLI
entailment: câu trả lời của LLM có được "chống lưng" bởi review nguồn không.

Local bench 17/07 (bench_mlguard.py, laptop 2 threads):
  - grounding VN 6/6 với decision rule contradiction-based (bịa: contra 0.98+,
    grounded: contra <=0.007); entailment-threshold đơn thuần chỉ 5/6.
  - injection zero-shot VN 4/7 (trượt cả 3 attack VN) -> KHÔNG làm injection
    ở đây; injection = regex T0 + Nova Micro judge (guardrails.py).
  - fp32 p50 ~1.8s, RSS ~1.1GB -> pod ask 1 vCPU / 1.5Gi.

Decision rule (đo được, không vibes):
  contra >= BLOCK_CONTRA          -> "block"  (mâu thuẫn nguồn = bịa/bóp méo)
  entail >= PASS_ENTAIL           -> "pass"
  còn lại (vùng neutral)          -> "judge"  (caller đưa Nova Micro phân xử)
"""
import json
import logging
import os
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

logger = logging.getLogger("ml-guard")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")

MODEL_ID = os.environ.get("ML_GUARD_MODEL", "MoritzLaurer/mDeBERTa-v3-base-mnli-xnli")
PORT = int(os.environ.get("ML_GUARD_PORT", "8090"))
BLOCK_CONTRA = float(os.environ.get("ML_GUARD_BLOCK_CONTRA", "0.5"))
PASS_ENTAIL = float(os.environ.get("ML_GUARD_PASS_ENTAIL", "0.3"))
MAX_SOURCE_CHARS = 6000   # top-K reviews; premise 512 token cap anyway
MAX_ANSWER_CHARS = 2000
TORCH_THREADS = int(os.environ.get("ML_GUARD_TORCH_THREADS", "2"))

_model_lock = threading.Lock()
_state = {"ready": False, "tok": None, "model": None, "torch": None}
# Poor-man metrics (Prometheus text format) — đủ cho scrape, không thêm dep.
_metrics = {"pass": 0, "block": 0, "judge": 0, "error": 0, "latency_sum": 0.0, "requests": 0}


def _load_model():
    import torch
    from transformers import AutoTokenizer, AutoModelForSequenceClassification, pipeline
    from presidio_analyzer import AnalyzerEngine
    from presidio_anonymizer import AnonymizerEngine
    torch.set_num_threads(TORCH_THREADS)
    tok = AutoTokenizer.from_pretrained(MODEL_ID)
    model = AutoModelForSequenceClassification.from_pretrained(MODEL_ID)
    model.eval()
    p_model = os.environ.get("PROMPT_GUARD_MODEL", "protectai/deberta-v3-base-prompt-injection-v2")
    prompt_guard = pipeline("text-classification", model=p_model)
    analyzer = AnalyzerEngine()
    anonymizer = AnonymizerEngine()
    _state.update(
        tok=tok, model=model, torch=torch, prompt_guard=prompt_guard, 
        analyzer=analyzer, anonymizer=anonymizer, ready=True
    )
    logger.info("models loaded: %s, %s (threads=%d)", MODEL_ID, p_model, TORCH_THREADS)


def nli_scores(premise, hypothesis):
    torch = _state["torch"]
    inp = _state["tok"](premise, hypothesis, truncation=True, max_length=512, return_tensors="pt")
    with torch.no_grad():
        logits = _state["model"](**inp).logits[0]
    probs = torch.softmax(logits, -1)
    # label order của model này: entailment, neutral, contradiction
    return probs[0].item(), probs[2].item()


def grounding_decision(source, answer):
    with _model_lock:  # 1 vCPU pod — serialize inference, tránh thrash
        entail, contra = nli_scores(source[:MAX_SOURCE_CHARS], answer[:MAX_ANSWER_CHARS])
    if contra >= BLOCK_CONTRA:
        action = "block"
    elif entail >= PASS_ENTAIL:
        action = "pass"
    else:
        action = "judge"
    return {"action": action, "entail": round(entail, 4), "contra": round(contra, 4)}


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):  # route access logs qua logger
        logger.debug(fmt, *args)

    def _json(self, code, payload):
        body = json.dumps(payload).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/healthz":
            self._json(200 if _state["ready"] else 503, {"ready": _state["ready"]})
        elif self.path == "/metrics":
            avg = _metrics["latency_sum"] / _metrics["requests"] if _metrics["requests"] else 0
            lines = [
                "# TYPE ml_guard_decisions_total counter",
                *(f'ml_guard_decisions_total{{action="{k}"}} {_metrics[k]}' for k in ("pass", "block", "judge", "error")),
                "# TYPE ml_guard_latency_avg_seconds gauge",
                f"ml_guard_latency_avg_seconds {avg:.4f}",
            ]
            body = ("\n".join(lines) + "\n").encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; version=0.0.4")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        else:
            self._json(404, {"error": "not found"})

    def do_POST(self):
        if self.path not in ("/v1/grounding", "/v1/protect"):
            return self._json(404, {"error": "not found"})
        if not _state["ready"]:
            return self._json(503, {"error": "model not ready"})
        try:
            length = int(self.headers.get("Content-Length", 0))
            req = json.loads(self.rfile.read(length))
            
            if self.path == "/v1/protect":
                return self._handle_protect(req)
                
            source, answer = req.get("source", ""), req.get("answer", "")
            if not source.strip() or not answer.strip():
                return self._json(400, {"error": "source and answer required"})
            t0 = time.perf_counter()
            result = grounding_decision(source, answer)
            dt = time.perf_counter() - t0
            _metrics[result["action"]] += 1
            _metrics["requests"] += 1
            _metrics["latency_sum"] += dt
            result["latency_ms"] = round(dt * 1000, 1)
            return self._json(200, result)
        except Exception as e:  # lỗi nội bộ -> caller fail-open, không treo trang
            if self.path == "/v1/grounding":
                _metrics["error"] += 1
            logger.error("error in %s: %s", self.path, e)
            return self._json(500, {"error": str(e)})

    def _handle_protect(self, req):
        text = req.get("text", "")
        if not text:
            return self._json(400, {"error": "text required"})
            
        t0 = time.perf_counter()
        
        # 1. Presidio PII
        anonymized_text = text
        analyzer = _state["analyzer"]
        anonymizer = _state["anonymizer"]
        results = analyzer.analyze(text=text, language='en')
        if results:
            anonymized = anonymizer.anonymize(text=text, analyzer_results=results)
            anonymized_text = anonymized.text
            
        # 2. Prompt Guard
        pipe = _state["prompt_guard"]
        pg_res = pipe(anonymized_text[:2000])
        label = pg_res[0]['label']
        score = pg_res[0]['score']
        
        dt = time.perf_counter() - t0
        return self._json(200, {
            "text": anonymized_text,
            "injection_label": label,
            "injection_score": score,
            "latency_ms": round(dt * 1000, 1)
        })


def main():
    threading.Thread(target=_load_model, daemon=True).start()  # serve /healthz trong lúc load
    server = ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    logger.info("ml-guard listening on :%d", PORT)
    server.serve_forever()


if __name__ == "__main__":
    main()
