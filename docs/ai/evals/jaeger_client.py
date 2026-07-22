"""Small Jaeger Query API client used by production evidence scripts."""

from __future__ import annotations

import re
import time
from urllib.parse import quote, urlsplit, urlunsplit

import requests


_TRACE_ID_RE = re.compile(r"^[0-9a-fA-F]{16,32}$")


def jaeger_ui_base(base_url: str) -> str:
    """Return the configured Jaeger UI base, including its base path.

    The TF deployment configures Jaeger with ``base_path: /jaeger/ui``.  Accept
    either the origin (``https://jaeger.example``) or the full UI base
    (``https://jaeger.example/jaeger/ui``) so callers cannot accidentally
    duplicate or omit that path.
    """
    raw = (base_url or "").strip()
    if not raw:
        return ""

    parsed = urlsplit(raw)
    path = parsed.path.rstrip("/")
    if not path:
        path = "/jaeger/ui"

    return urlunsplit((parsed.scheme, parsed.netloc, path, "", ""))


def fetch_trace(
    trace_id: str,
    base_url: str,
    *,
    request_timeout: float = 5.0,
    wait_timeout: float = 10.0,
    poll_interval: float = 0.5,
    required_operation: str | None = "shopping_copilot.chat",
):
    """Fetch one trace, polling until its request span has been exported."""
    normalized_trace_id = (trace_id or "").strip()
    ui_base = jaeger_ui_base(base_url)
    if not ui_base or not _TRACE_ID_RE.fullmatch(normalized_trace_id):
        return None

    url = f"{ui_base}/api/traces/{quote(normalized_trace_id, safe='')}"
    deadline = time.monotonic() + max(0.0, wait_timeout)
    latest_payload = None

    while True:
        try:
            response = requests.get(url, timeout=request_timeout)
        except requests.RequestException:
            return None

        if response.status_code == 200:
            try:
                payload = response.json()
            except ValueError:
                return None
            if isinstance(payload, dict) and payload.get("data"):
                latest_payload = payload
                operation_names = {
                    span.get("operationName", "")
                    for trace_data in payload["data"]
                    if isinstance(trace_data, dict)
                    for span in trace_data.get("spans", [])
                    if isinstance(span, dict)
                }
                if required_operation is None or required_operation in operation_names:
                    return payload
        elif response.status_code != 404:
            return None

        if time.monotonic() >= deadline:
            return latest_payload
        time.sleep(max(0.05, poll_interval))


def count_spans(trace_json) -> int:
    """Count all spans across every trace returned by the Jaeger API."""
    if not isinstance(trace_json, dict):
        return 0
    return sum(
        len(trace.get("spans", []))
        for trace in trace_json.get("data", [])
        if isinstance(trace, dict)
    )

def summarize_spans(trace_json):
    if not isinstance(trace_json, dict) or not trace_json.get("data"):
        return []

    known_spans = {
        "shopping_copilot.chat",
        "guardrail_input",
        "bedrock_converse",
        "tool_call",
        "guardrail_citation_validation",
        "guardrail_output_grounding",
    }

    summary = []
    for trace_data in trace_json["data"]:
        for span in trace_data.get("spans", []):
            name = span.get("operationName", "")
            if name not in known_spans:
                continue
            attrs = {}
            for tag in span.get("tags", []):
                key = tag.get("key", "")
                if key.startswith(("copilot.", "guardrail.", "gen_ai.", "tool.")):
                    attrs[key] = tag.get("value")
            summary.append({"name": name, "attributes": attrs})

    return summary


def jaeger_ui_link(trace_id: str, base_url: str) -> str:
    normalized_trace_id = (trace_id or "").strip()
    ui_base = jaeger_ui_base(base_url)
    if not ui_base or not _TRACE_ID_RE.fullmatch(normalized_trace_id):
        return ""
    return f"{ui_base}/trace/{quote(normalized_trace_id, safe='')}"
