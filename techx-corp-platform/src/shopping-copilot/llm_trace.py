"""LLM Trace Store — Valkey-backed black box for model tier (MANDATE-24).

ponytail: single-file trace store reusing existing Valkey connection.
Upgrade path: Postgres if persistence needed beyond 7d TTL.
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
from datetime import datetime, timezone
from typing import Optional

from opentelemetry import metrics

logger = logging.getLogger(__name__)

meter = metrics.get_meter("model-gateway")
gateway_requests = meter.create_counter("llm.gateway.requests", unit="1")
gateway_latency = meter.create_histogram("llm.gateway.latency", unit="ms")
gateway_input_tokens = meter.create_counter("llm.gateway.input_tokens", unit="1")
gateway_output_tokens = meter.create_counter("llm.gateway.output_tokens", unit="1")
gateway_cost = meter.create_counter("llm.gateway.estimated_cost", unit="1")

# Pricing per 1M tokens (source: docs/ai/03_specs/model_gateway_ab_testing.md)
_PRICING = {
    "amazon.nova-lite-v1:0":  {"input": 0.00006,  "output": 0.00024},
    "amazon.nova-pro-v1:0":   {"input": 0.0008,   "output": 0.0032},
    "amazon.nova-micro-v1:0": {"input": 0.000035, "output": 0.00014},
}

TRACE_TTL = 604800  # 7 days

# PII patterns — ponytail: regex-based, upgrade to ml-guard Presidio gRPC for production
_PII_PATTERNS = [
    re.compile(r'[\w.\-]+@[\w\-]+\.\w{2,}'),
    re.compile(r'\b\d{3}[-.]?\d{2}[-.]?\d{4}\b'),
    re.compile(r'\b(?:\d[ -]*?){13,16}\b'),
]


def _pricing_key(model_id: str) -> dict:
    for prefix, price in _PRICING.items():
        if model_id.startswith(prefix):
            return price
    return {"input": 0.00006, "output": 0.00024}


def compute_cost(model_id: str, usage: dict) -> float:
    price = _pricing_key(model_id)
    return (usage.get("inputTokens", 0) * price["input"] +
            usage.get("outputTokens", 0) * price["output"]) / 1_000_000


def _public_model_id(model_id: str) -> str:
    value = str(model_id or "unknown")
    return value.rsplit("/", 1)[-1] if value.startswith("arn:") else value

def record_gateway_metrics(model_id: str, task_type: str, status: str,
                           usage: dict, latency_s: float) -> None:
    """Record low-cardinality gateway telemetry without affecting serving."""
    try:
        attributes = {
            "model_id": _public_model_id(model_id),
            "task_type": task_type,
            "status": status,
        }
        gateway_requests.add(1, attributes)
        gateway_latency.record(max(0.0, latency_s) * 1000, attributes)
        gateway_input_tokens.add(max(0, usage.get("inputTokens", 0)), attributes)
        gateway_output_tokens.add(max(0, usage.get("outputTokens", 0)), attributes)
        gateway_cost.add(max(0.0, compute_cost(model_id, usage)), attributes)
    except Exception:
        logger.exception("record_gateway_metrics failed")


def mask_pii(text: str) -> str:
    """Hash PII markers before storing in trace. Returns masked text."""
    for pattern in _PII_PATTERNS:
        for match in pattern.findall(text):
            h = hashlib.sha256(match.encode()).hexdigest()[:12]
            text = text.replace(match, f"<PII-{h}>")
    return text


def _prompt_hash(messages: list[dict]) -> str:
    """Deterministic content hash — same prompt → same hash, no raw prompt stored."""
    raw = json.dumps(messages, sort_keys=True, default=str)
    masked = mask_pii(raw)
    return hashlib.sha256(masked.encode()).hexdigest()[:16]


def record_trace(valkey_client, trace_data: dict) -> bool:
    """Write trace record to Valkey. Fire-and-forget from thread pool. Never blocks."""
    try:
        trace_id = trace_data.get("trace_id", "")
        if not trace_id:
            logger.warning("record_trace: empty trace_id, skipping")
            return False
        payload = json.dumps(trace_data, default=str)
        valkey_client.setex(f"trace:{trace_id}", TRACE_TTL, payload)
        sid = trace_data.get("session_id", "")
        if sid:
            valkey_client.sadd(f"trace:session:{sid}", trace_id)
            valkey_client.expire(f"trace:session:{sid}", TRACE_TTL)
        return True
    except Exception:
        logger.exception("record_trace failed")
        return False


def fetch_trace(valkey_client, trace_id: str) -> Optional[dict]:
    try:
        raw = valkey_client.get(f"trace:{trace_id}")
        return json.loads(raw) if raw else None
    except Exception:
        logger.exception("fetch_trace failed")
        return None


def fetch_session_traces(valkey_client, session_id: str) -> list[dict]:
    try:
        ids = valkey_client.smembers(f"trace:session:{session_id}")
        traces = []
        for tid in ids:
            tid_str = tid.decode() if isinstance(tid, bytes) else tid
            t = fetch_trace(valkey_client, tid_str)
            if t:
                traces.append(t)
        traces.sort(key=lambda t: t.get("timestamp_utc", ""))
        return traces
    except Exception:
        logger.exception("fetch_session_traces failed")
        return []


def build_trace_record(*, trace_id: str, session_id: str, model_id: str,
                       usage: dict, latency_s: float, outcome: str,
                       tool_calls: list[str], surface: str,
                       messages: Optional[list[dict]] = None) -> dict:
    return {
        "trace_id": trace_id,
        "session_id": session_id,
        "model_id": model_id,
        "tokens_in": usage.get("inputTokens", 0),
        "tokens_out": usage.get("outputTokens", 0),
        "latency_ms": int(latency_s * 1000),
        "cost_usd": round(compute_cost(model_id, usage), 8),
        "outcome": outcome,
        "tool_calls": tool_calls,
        "surface": surface,
        "prompt_hash": _prompt_hash(messages) if messages else "",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
    }


def aggregate_traces(valkey_client) -> list[dict]:
    """Return cost/latency summary grouped by model+surface. For aggregate view."""
    rows: dict[tuple, dict] = {}
    try:
        for key in valkey_client.scan_iter("trace:*", count=100):
            raw = valkey_client.get(key)
            if not raw:
                continue
            t = json.loads(raw)
            group = (t.get("model_id", "?"), t.get("surface", "?"))
            if group not in rows:
                rows[group] = {"model_id": group[0], "surface": group[1],
                               "count": 0, "total_tokens_in": 0, "total_tokens_out": 0,
                               "total_cost_usd": 0.0, "total_latency_ms": 0}
            r = rows[group]
            r["count"] += 1
            r["total_tokens_in"] += t.get("tokens_in", 0)
            r["total_tokens_out"] += t.get("tokens_out", 0)
            r["total_cost_usd"] += t.get("cost_usd", 0)
            r["total_latency_ms"] += t.get("latency_ms", 0)
    except Exception:
        logger.exception("aggregate_traces failed")
    result = []
    for r in rows.values():
        n = r["count"]
        result.append({
            "model_id": r["model_id"],
            "surface": r["surface"],
            "call_count": n,
            "total_tokens_in": r["total_tokens_in"],
            "total_tokens_out": r["total_tokens_out"],
            "total_cost_usd": round(r["total_cost_usd"], 8),
            "avg_latency_ms": round(r["total_latency_ms"] / n, 1) if n else 0,
        })
    result.sort(key=lambda r: r["total_cost_usd"], reverse=True)
    return result
