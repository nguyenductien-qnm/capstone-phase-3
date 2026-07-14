# Guardrails cho tang AI (de bai Phan A): chan prompt-injection nhet trong review,
# loc PII, chan lo system prompt. Noi dung review la DU LIEU KHONG TIN CAY.
import json
import re

INJECTION_PATTERNS = re.compile(
    r"(ignore\s+(all\s+|any\s+)?(previous|prior|above)\s+(instructions?|prompts?)"
    r"|disregard\s+(the\s+)?(system|previous)\s+prompt"
    r"|you\s+are\s+now\s+"
    r"|new\s+instructions?\s*:"
    r"|reveal\s+(your\s+)?(system\s+prompt|instructions?|api\s+keys?)"
    r"|^\s*system\s*:)",
    re.IGNORECASE | re.MULTILINE)
PII_EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
PII_PHONE = re.compile(r"\+?\d[\d\s().-]{7,}\d")
MAX_FIELD_CHARS = 1000  # tran per-field, khong cat giua JSON


def sanitize_text(text):
    """Loc 1 chuoi khong tin cay truoc khi dua vao prompt LLM."""
    text = PII_EMAIL.sub("[email]", text)
    text = PII_PHONE.sub("[phone]", text)
    text = INJECTION_PATTERNS.sub("[filtered]", text)
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
    """Sanitize moi string field trong 1 JSON string (tool result) — giu cau truc JSON hop le."""
    try:
        return json.dumps(_walk(json.loads(json_str)))
    except Exception:
        return json.dumps({"error": "unparseable tool result was withheld by guardrail"})


def leaks_system_prompt(text, system_prompt):
    """Output guard: chan tra loi chua noi dung system prompt (>=40 ky tu dau trung khop)."""
    if not text:
        return False
    return system_prompt[:40].lower() in text.lower()
