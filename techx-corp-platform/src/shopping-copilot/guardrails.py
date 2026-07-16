# Guardrails cho tầng AI (TF1-61, MANDATE-06) — Bedrock Guardrails làm engine.
#
# v4 (retire v3 hand-rolled): thay ~700 dòng bespoke (homoglyph map, leetspeak,
# base64, Shannon entropy, _KNOWN_ATTACK_CORPUS + Titan semantic guard,
# SessionGuardrail, classify_input_llm, INJECTION_PATTERNS khổng lồ) bằng
# managed Amazon Bedrock Guardrails:
#   INPUT  rail: prompt-attack + PII(ANONYMIZE) + denied-topic (system-prompt extraction)
#   OUTPUT rail: contextual-grounding (faithfulness) + PII(ANONYMIZE)
# Lý do (ADR-012): mandate "đừng quăng model to cho xong" — v3 tự chạy Titan
# embed + Nova judge/request. Bedrock Guardrails là policy engine managed, ít
# code hơn, có contextual-grounding (thứ v3 chỉ giả lập bằng citation-hack).
#
# Nội dung review = DỮ LIỆU KHÔNG TIN CẬY. Tool allow-list + confirmation gate
# cho hành động ghi nằm ở agent.py (app), KHÔNG phải guardrail engine.
#
# Phase-2 (flag llmLocalMlGuard, CDO đã confirm cấp pod): thêm local ML gate
# (Prompt Guard 2 / Presidio NER) TRƯỚC Bedrock — chỉ bật khi eval đo được
# Bedrock để hở gap (metric ml_vs_bedrock_disagreement). Chưa implement.

import json
import os
import re
import logging

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Config — guardrail id/version tiêm qua env (values-aio-llm.yaml, AI-owned).
# ---------------------------------------------------------------------------
GUARDRAIL_ID = os.environ.get("BEDROCK_GUARDRAIL_ID", "")
GUARDRAIL_VERSION = os.environ.get("BEDROCK_GUARDRAIL_VERSION", "DRAFT")
# Feature flag: bật/tắt Bedrock guardrail (mặc định bật khi có id). Tắt → fallback
# về pre-filter regex (degrade an toàn, không treo).
GUARDRAIL_ENABLED = bool(GUARDRAIL_ID) and (
    os.environ.get("LLM_BEDROCK_GUARDRAIL", "true").lower() == "true"
)

MAX_FIELD_CHARS = 1000              # trần per-field cho tool result
GROUNDING_MAX_SOURCE_CHARS = 90000  # < 100k limit; cap top-K review

# ---------------------------------------------------------------------------
# Thin deterministic pre-filter — free, short-circuit rác trước khi trả tiền Bedrock.
# CHỈ vài mẫu hiển nhiên; regex khổng lồ v3 đã bỏ (Bedrock prompt-attack lo phần khó).
# ---------------------------------------------------------------------------
_OBVIOUS_INJECTION = re.compile(
    r"ignore\s+(all\s+|any\s+)?(previous|prior|above)\s+(instructions?|prompts?)"
    r"|reveal\s+(your\s+)?(system\s+prompt|instructions?)"
    r"|bỏ\s+qua\s+(các\s+)?(lệnh|hướng\s+dẫn)"
    r"|in\s+ra\s+(toàn\s+bộ\s+)?system\s+prompt",
    re.IGNORECASE,
)

# PII regex — fallback khi guardrail tắt/lỗi. Thứ tự: CC trước Phone.
_PII_CC = re.compile(r'\b(?:\d[ -]*){13,16}\b')
_PII_EMAIL = re.compile(r'[\w.+-]+@[\w-]+\.[\w.-]+')
_PII_PHONE = re.compile(r'\+?\d[\d\s().-]{7,}\d')

_NUMBER_PATTERN = re.compile(r'\b\d+\.?\d*%?\b')


# ---------------------------------------------------------------------------
# NEW primary path — Bedrock ApplyGuardrail wrappers.
# ---------------------------------------------------------------------------

def _apply_guardrail(bedrock_client, source, content_blocks):
    """Gọi ApplyGuardrail standalone. source = 'INPUT' | 'OUTPUT'.
    trace=disabled (mặc định API) — KHÔNG bật FULL/trace ở prod vì lộ raw PII.
    Trả assessment dict, hoặc None khi lỗi/tắt (caller xử fail-closed/open)."""
    if not GUARDRAIL_ENABLED:
        return None
    try:
        return bedrock_client.apply_guardrail(
            guardrailIdentifier=GUARDRAIL_ID,
            guardrailVersion=GUARDRAIL_VERSION,
            source=source,
            content=content_blocks,
        )
    except Exception as e:
        logger.error("ApplyGuardrail(%s) error: %s", source, e)
        return None


def apply_guardrail_input(bedrock_client, text):
    """INPUT rail: prompt-attack + PII mask + denied-topic trên text KHÔNG tin cậy
    (review / user msg). Trả (blocked: bool, output_text). Fail-CLOSED: guardrail
    lỗi khi ĐANG bật → coi như blocked (an toàn). Guardrail tắt → pre-filter regex."""
    if not text or not text.strip():
        return (False, text)
    if not GUARDRAIL_ENABLED:
        blocked = bool(_OBVIOUS_INJECTION.search(text))
        return (blocked, redact_pii(text))

    resp = _apply_guardrail(bedrock_client, "INPUT", [{"text": {"text": text[:MAX_FIELD_CHARS * 25]}}])
    if resp is None:
        logger.warning("Input guardrail fail-closed (Bedrock error while enabled).")
        return (True, text)
    outputs = resp.get("outputs", [])
    masked = outputs[0].get("text", text) if outputs else text
    blocked = resp.get("action") == "GUARDRAIL_INTERVENED" and _is_blocking(resp)
    return (blocked, masked)


def apply_guardrail_output(bedrock_client, answer, source_text, query):
    """OUTPUT rail: contextual-grounding (faithfulness) + PII mask trên câu trả lời.
    Trả (blocked: bool, output_text). blocked=True → caller fallback
    "review không đề cập". Fail-OPEN cho grounding (additive) nhưng PII vẫn
    redact regex — không để treo trang. source_text = review nguồn."""
    if not answer or not answer.strip():
        return (False, answer)
    if not GUARDRAIL_ENABLED:
        return (False, redact_pii(answer))

    content = [
        {"text": {"text": (source_text or "")[:GROUNDING_MAX_SOURCE_CHARS], "qualifiers": ["grounding_source"]}},
        {"text": {"text": (query or "")[:1000], "qualifiers": ["query"]}},
        {"text": {"text": answer[:5000], "qualifiers": ["guard_content"]}},
    ]
    resp = _apply_guardrail(bedrock_client, "OUTPUT", content)
    if resp is None:
        return (False, redact_pii(answer))  # fail-open, vẫn mask PII cục bộ
    outputs = resp.get("outputs", [])
    masked = outputs[0].get("text", answer) if outputs else answer
    blocked = resp.get("action") == "GUARDRAIL_INTERVENED" and _is_blocking(resp)
    return (blocked, masked)


def _is_blocking(resp):
    """True nếu assessment có policy BLOCK (không phải chỉ ANONYMIZE/mask).
    Grounding dưới ngưỡng → coi là blocking. PII ANONYMIZE → KHÔNG block (đã mask)."""
    for a in resp.get("assessments", []):
        cg = a.get("contextualGroundingPolicy", {}).get("filters", [])
        if any(f.get("action") == "BLOCKED" for f in cg):
            return True
        tp = a.get("topicPolicy", {}).get("topics", [])
        if any(t.get("action") == "BLOCKED" for t in tp):
            return True
        cp = a.get("contentPolicy", {}).get("filters", [])
        if any(f.get("action") == "BLOCKED" for f in cp):
            return True
    return False


# ---------------------------------------------------------------------------
# Backward-compatible public API — servers import these; giữ tên, thu gọn ruột.
# ---------------------------------------------------------------------------

def redact_pii(text):
    """Redact PII bằng regex (fallback layer, dùng khi guardrail tắt/lỗi)."""
    if not text:
        return text
    text = _PII_CC.sub('[REDACTED_CC]', text)
    text = _PII_EMAIL.sub('[REDACTED_EMAIL]', text)
    text = _PII_PHONE.sub('[REDACTED_PHONE]', text)
    return text


def sanitize_text(text):
    """Thin pre-filter 1 chuỗi không tin cậy: length cap + PII redact + lọc mẫu
    injection hiển nhiên. KHÔNG thay Bedrock — chạy trước, rẻ, offline-safe."""
    if not text:
        return text
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


def sanitize_json_for_llm(json_str):
    """Sanitize mọi string field trong tool-result JSON, giữ cấu trúc hợp lệ."""
    try:
        return json.dumps(_walk(json.loads(json_str)))
    except Exception:
        return json.dumps({"error": "unparseable tool result was withheld by guardrail"})


def leaks_system_prompt(output_text, system_prompt, window_words=6):
    """Output guard rẻ: sliding-window N-từ của output có nằm trong system_prompt
    không. Bổ trợ cho denied-topic của Bedrock (bắt leak verbatim, không bắt
    paraphrase — đó là việc của Bedrock)."""
    if not output_text or not system_prompt:
        return False

    def _norm(t):
        return " ".join(re.sub(r'[^\w\s]', ' ', t.lower()).split())

    out_words = _norm(output_text).split()
    prompt_norm = _norm(system_prompt)
    if not out_words or not prompt_norm:
        return False
    windows = (
        [" ".join(out_words[i:i + window_words]) for i in range(len(out_words) - window_words + 1)]
        if len(out_words) >= window_words else [" ".join(out_words)]
    )
    for w in windows:
        if len(w) >= 20 and w in prompt_norm:
            logger.warning("System prompt leakage detected (matched: %r…)", w[:30])
            return True
    return False


def validate_citations(llm_output, tool_results):
    """Kiểm số cụ thể (>=3) trong output có tồn tại trong tool results không.
    Số bịa → thay '[unverified]'. Bổ trợ Bedrock grounding (rẻ, deterministic)."""
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


# --- Deprecated shims: tên cũ server còn import; route qua Bedrock hoặc no-op. ---

def detect_prompt_injection_llm(bedrock_client, text, *, fail_closed=True):
    """DEPRECATED → Bedrock prompt-attack filter. Giữ chữ ký cho tương thích.
    Route qua apply_guardrail_input khi guardrail bật; tắt → pre-filter regex."""
    if not text or not text.strip():
        return False
    if not GUARDRAIL_ENABLED:
        return bool(_OBVIOUS_INJECTION.search(text))
    blocked, _ = apply_guardrail_input(bedrock_client, text)
    return blocked


def detect_semantic_similarity_to_known_attacks(bedrock_client, text):
    """DEPRECATED → thay bằng Bedrock prompt-attack filter (managed classifier).
    No-op giữ import sống. Xoá call site trong bước wiring."""
    return {"flagged": False, "max_similarity": 0.0, "matched": None}
