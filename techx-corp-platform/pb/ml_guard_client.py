"""Shared ml-guard v2 client — dùng chung cho product-reviews và shopping-copilot.

Thin sync gRPC wrappers gọi ml-guard trung tâm + các pure function rẻ chạy local
(regex PII, leak detector, citation check). Mỗi service import qua shim
`guardrails.py` trong thư mục service để giữ nguyên import path cũ.
"""
import json
import logging
import os
import re

import grpc

import ml_guard_pb2
import ml_guard_pb2_grpc

logger = logging.getLogger(__name__)

ML_GUARD_URL = os.environ.get("ML_GUARD_URL", "ml-guard:8090").replace("http://", "")
ML_GUARD_TIMEOUT = float(os.environ.get("ML_GUARD_TIMEOUT", "25.0"))
MAX_FIELD_CHARS = 1000

_PII_CC = re.compile(r'\b(?:\d[ -]*){13,16}\b')
_PII_EMAIL = re.compile(r'[\w.+-]+@[\w-]+\.[\w.-]+')
_PII_PHONE = re.compile(r'\+?\d[\d\s().-]{7,}\d')
_NUMBER_PATTERN = re.compile(r'\b\d+\.?\d*%?\b')
_INVISIBLE_CHARS_RE = re.compile("[\u200b-\u200f\u2060\ufeff]")
_OBVIOUS_INJECTION = re.compile(
    r"ignore\s+(all\s+|any\s+)?(previous|prior|above)\s+(instructions?|prompts?)"
    r"|reveal\s+(your\s+)?(system\s+prompt|instructions?)"
    r"|bỏ\s+qua\s+(các\s+|mọi\s+|toàn\s+bộ\s+)?(lệnh|hướng\s+dẫn)"
    r"|in\s+ra\s+(toàn\s+bộ\s+)?system\s+prompt"
    r"|tiết\s+lộ\s+(toàn\s+bộ\s+)?(chỉ\s+dẫn|hướng\s+dẫn|bí\s+mật)"
    r"|developer\s+mode"
    r"|disregard.*(safety|guidelines|instructions)"
    r"|you\s+are\s+now\s+(an?\s+)?(admin|root|developer|dan)\b",
    re.IGNORECASE,
)

# ---------------------------------------------------------------------------
# Thin sync wrappers calling central ml-guard v2
# ---------------------------------------------------------------------------

_channel = None
_stub = None


def _get_stub():
    # gRPC channel là long-lived, multiplex — tạo 1 lần, tái dùng mọi request.
    global _channel, _stub
    if _stub is None:
        _channel = grpc.insecure_channel(ML_GUARD_URL)
        _stub = ml_guard_pb2_grpc.MLGuardServiceStub(_channel)
    return _stub


def apply_guardrail_input(bedrock_client, text):
    if not text or not text.strip():
        return (False, text)
    # T0: regex chặn injection hiển nhiên ngay tại client — vẫn chặn khi ml-guard outage,
    # và khỏi tốn round-trip cho case rõ ràng.
    if _OBVIOUS_INJECTION.search(text):
        return (True, sanitize_text(text))
    try:
        stub = _get_stub()
        req = ml_guard_pb2.CheckInputRequest(text=text)
        resp = stub.CheckInput(req, timeout=ML_GUARD_TIMEOUT)
        return (resp.blocked, resp.sanitized_text)
    except Exception as e:
        logger.warning("CheckInput fallback (error): %s", e)
        return (False, sanitize_text(text))


def apply_guardrail_output(bedrock_client, answer, source_text, query):
    if not answer or not answer.strip():
        return (False, answer)
    try:
        stub = _get_stub()
        req = ml_guard_pb2.CheckOutputRequest(answer=answer, grounding_source=source_text, query=query)
        resp = stub.CheckOutput(req, timeout=ML_GUARD_TIMEOUT)
        return (resp.blocked, resp.sanitized_text)
    except Exception as e:
        logger.warning("CheckOutput fallback (error): %s", e)
        return (False, redact_pii(answer))


def sanitize_json_for_llm(json_str):
    try:
        stub = _get_stub()
        req = ml_guard_pb2.SanitizeReviewsRequest(json_payload=json_str)
        resp = stub.SanitizeReviews(req, timeout=ML_GUARD_TIMEOUT)
        return resp.sanitized_json
    except Exception as e:
        logger.warning("SanitizeReviews fallback (error): %s", e)
        return _sanitize_json_local(json_str)


# ---------------------------------------------------------------------------
# Local lightweight pure functions (fallback khi ml-guard unreachable)
# ---------------------------------------------------------------------------

def redact_pii(text):
    if not text:
        return text
    text = _PII_CC.sub('[REDACTED_CC]', text)
    text = _PII_EMAIL.sub('[REDACTED_EMAIL]', text)
    text = _PII_PHONE.sub('[REDACTED_PHONE]', text)
    return text


def sanitize_text(text):
    """Pre-filter rẻ, offline-safe: length cap + PII redact + lọc mẫu injection
    hiển nhiên. Bản đầy đủ (Presidio/NLI) nằm server-side trong ml-guard."""
    if not text:
        return text
    text = _INVISIBLE_CHARS_RE.sub("", text)
    text = redact_pii(text)
    if _OBVIOUS_INJECTION.search(text):
        text = _OBVIOUS_INJECTION.sub('[filtered]', text)
    return text[:MAX_FIELD_CHARS]


def _walk(node):
    if isinstance(node, str):
        return sanitize_text(node)
    if isinstance(node, list):
        return [_walk(x) for x in node]
    if isinstance(node, dict):
        return {k: _walk(v) for k, v in node.items()}
    return node


def _sanitize_json_local(json_str):
    try:
        return json.dumps(_walk(json.loads(json_str)))
    except Exception:
        return json.dumps({"error": "unparseable tool result was withheld by guardrail"})


def leaks_system_prompt(output_text, system_prompt, window_words=8, allowlist=None):
    """Output guard rẻ: sliding-window N-từ của output có nằm trong system_prompt
    không (bắt leak verbatim, không bắt paraphrase — việc của grounding gate).

    allowlist: câu template mà system_prompt CHỦ ĐỘNG yêu cầu model nói nguyên văn
    cho khách (vd. câu xác nhận giỏ hàng) — không phải bí mật bị lộ. Window nằm
    trong allowlist thì bỏ qua, các window khác vẫn bị bắt bình thường."""
    if not output_text or not system_prompt:
        return False

    def _norm(t):
        return " ".join(re.sub(r'[^\w\s]', ' ', t.lower()).split())

    out_words = _norm(output_text).split()
    prompt_norm = _norm(system_prompt)
    if not out_words or not prompt_norm:
        return False
    allow_norm = [_norm(a) for a in (allowlist or [])]
    windows = (
        [" ".join(out_words[i:i + window_words]) for i in range(len(out_words) - window_words + 1)]
        if len(out_words) >= window_words else [" ".join(out_words)]
    )
    for w in windows:
        if len(w) >= 20 and w in prompt_norm:
            if any(w in a for a in allow_norm):
                continue
            logger.warning("System prompt leakage detected (matched: %r…)", w[:30])
            return True
    return False


def validate_citations(llm_output, tool_results):
    """Kiểm số cụ thể (>=3) trong output có tồn tại trong tool results không.
    Số bịa → thay '[unverified]'. Rẻ, deterministic, bổ trợ grounding gate."""
    if not llm_output or not tool_results:
        return (True, llm_output)
    all_text = ' '.join(str(r) for r in tool_results)
    is_valid, cleaned = True, llm_output
    for num_str in _NUMBER_PATTERN.findall(llm_output):
        try:
            if float(num_str.rstrip('%')) < 3:
                continue
        except ValueError:
            continue
        if num_str not in all_text:
            is_valid = False
            cleaned = cleaned.replace(num_str, '[unverified]', 1)
    return (is_valid, cleaned)
