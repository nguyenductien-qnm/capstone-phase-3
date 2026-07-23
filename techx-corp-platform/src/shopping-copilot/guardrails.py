import json
import logging
import os
import re
import grpc
from grpc.aio import insecure_channel
try:
    from opentelemetry.propagate import inject
except ImportError:
    def inject(headers): pass

import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../pb')))
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

# ---------------------------------------------------------------------------
# Thin Async wrappers calling central ml-guard v2
# ---------------------------------------------------------------------------

async def _get_stub():
    channel = insecure_channel(ML_GUARD_URL)
    return ml_guard_pb2_grpc.MLGuardServiceStub(channel), channel

async def apply_guardrail_input(bedrock_client, text):
    if not text or not text.strip():
        return (False, text)
    try:
        stub, channel = await _get_stub()
        req = ml_guard_pb2.CheckInputRequest(text=text)
        resp = await stub.CheckInput(req, timeout=ML_GUARD_TIMEOUT)
        await channel.close()
        return (resp.blocked, resp.sanitized_text)
    except Exception as e:
        logger.warning("CheckInput fallback (error): %s", e)
        masked = redact_pii(text)
        return (False, masked)

async def apply_guardrail_output(bedrock_client, answer, source_text, query):
    if not answer or not answer.strip():
        return (False, answer)
    try:
        stub, channel = await _get_stub()
        req = ml_guard_pb2.CheckOutputRequest(answer=answer, grounding_source=source_text, query=query)
        resp = await stub.CheckOutput(req, timeout=ML_GUARD_TIMEOUT)
        await channel.close()
        return (resp.blocked, resp.sanitized_text)
    except Exception as e:
        logger.warning("CheckOutput fallback (error): %s", e)
        masked = redact_pii(answer)
        return (False, masked)

async def sanitize_json_for_llm(json_str):
    try:
        stub, channel = await _get_stub()
        req = ml_guard_pb2.SanitizeReviewsRequest(json_payload=json_str)
        resp = await stub.SanitizeReviews(req, timeout=ML_GUARD_TIMEOUT)
        await channel.close()
        return resp.sanitized_json
    except Exception as e:
        logger.warning("SanitizeReviews fallback (error): %s", e)
        return json.dumps({"error": "unparseable tool result was withheld by guardrail"})


# ---------------------------------------------------------------------------
# Local lightweight pure functions
# ---------------------------------------------------------------------------

def redact_pii(text):
    if not text:
        return text
    text = _PII_CC.sub('[REDACTED_CC]', text)
    text = _PII_EMAIL.sub('[REDACTED_EMAIL]', text)
    text = _PII_PHONE.sub('[REDACTED_PHONE]', text)
    return text

def leaks_system_prompt(output_text, system_prompt, window_words=8):
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
