import os

os.environ.setdefault("DB_CONNECTION_STRING", "host=test user=test password=test dbname=test")

import product_reviews_server as server
from unittest.mock import MagicMock


class FakeBedrock:
    def __init__(self, scripted):
        self._scripted = list(scripted)

    def converse(self, **kwargs):
        item = self._scripted.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


def _response(input_tokens=1000, output_tokens=500):
    return {
        "usage": {"inputTokens": input_tokens, "outputTokens": output_tokens},
        "output": {"message": {"content": [{"text": "ok"}]}},
    }


def _configure(monkeypatch, primary, fallback):
    monkeypatch.setenv("LLM_REVIEWS_MAIN_MODEL", "amazon.nova-pro-v1:0")
    monkeypatch.setenv("LLM_REVIEWS_FALLBACK_MODEL", "amazon.nova-lite-v1:0")
    monkeypatch.setenv("LLM_REVIEWS_MAX_RETRIES", "0")
    monkeypatch.setenv("LLM_REVIEWS_FALLBACK_RETRIES", "0")
    monkeypatch.setattr(server, "get_bedrock_primary_client", lambda: primary)
    monkeypatch.setattr(server, "get_bedrock_fallback_client", lambda: fallback)
    monkeypatch.setattr(server, "check_feature_flag", lambda name, default=False: default)
    monkeypatch.setattr(server, "_record_bedrock_metrics", lambda *args, **kwargs: None)
    server._cb_state.update({"failures": 0, "open_until": 0.0})


def test_fallback_returns_trace_metadata_for_actual_model(monkeypatch):
    _configure(monkeypatch, FakeBedrock([RuntimeError("primary failed")]), FakeBedrock([_response()]))

    response, model_id, outcome = server.invoke_bedrock_converse_with_fallback(
        messages=[{"role": "user", "content": [{"text": "hi"}]}],
        system_prompt="system",
    )

    assert response["usage"]["inputTokens"] == 1000
    assert model_id == "amazon.nova-lite-v1:0"
    assert outcome == "fallback"


def test_failed_fallback_returns_error_metadata(monkeypatch):
    _configure(
        monkeypatch,
        FakeBedrock([RuntimeError("primary failed")]),
        FakeBedrock([RuntimeError("fallback failed")]),
    )

    response, model_id, outcome = server.invoke_bedrock_converse_with_fallback(
        messages=[{"role": "user", "content": [{"text": "hi"}]}],
        system_prompt="system",
    )

    assert response is None
    assert model_id == "amazon.nova-lite-v1:0"
    assert outcome == "error"

import json
from contextlib import contextmanager
from opentelemetry.trace import SpanContext, TraceFlags


class FakeSpan:
    def __init__(self, trace_id):
        self._context = SpanContext(
            trace_id=trace_id,
            span_id=1,
            is_remote=False,
            trace_flags=TraceFlags(TraceFlags.SAMPLED),
        )

    def get_span_context(self):
        return self._context

    def set_attribute(self, *_args, **_kwargs):
        pass


class FakeTracer:
    def __init__(self, span):
        self._span = span

    @contextmanager
    def start_as_current_span(self, _name):
        yield self._span


def test_active_request_trace_id_survives_early_refusal(monkeypatch):
    trace_id = int("1234567890abcdef1234567890abcdef", 16)
    monkeypatch.setattr(server, "tracer", FakeTracer(FakeSpan(trace_id)))
    monkeypatch.setattr(server, "get_bedrock_primary_client", lambda: object())
    monkeypatch.setattr(server, "apply_guardrail_input", lambda *_args: (True, "blocked"))

    response = server.get_ai_assistant_response("product-1", "unsafe")

    assert response.trace_id == "1234567890abcdef1234567890abcdef"


def test_model_trace_step_contains_available_telemetry():
    step = server._model_trace_step(
        response=_response(input_tokens=1000, output_tokens=500),
        model_id="amazon.nova-lite-v1:0",
        outcome="fallback",
        latency_ms=25,
    )

    detail = json.loads(step.detail)
    assert step.status == "fallback"
    assert detail["model_id"] == "amazon.nova-lite-v1:0"
    assert detail["tokens_in"] == 1000
    assert detail["tokens_out"] == 500
    assert detail["cost_usd"] > 0
    assert detail["outcome"] == "fallback"
    assert detail["timestamp_utc"]


def test_cache_trace_step_exposes_only_cached_evidence():
    step = server._cache_trace_step("hit_exact", {
        "model_ver": "amazon.nova-pro-v1:0",
        "created_at": "2026-07-30T00:00:00+00:00",
    })

    detail = json.loads(step.detail)
    assert step.status == "hit_exact"
    assert detail == {
        "model_id": "amazon.nova-pro-v1:0",
        "outcome": "hit_exact",
        "timestamp": "2026-07-30T00:00:00+00:00",
    }

class FakeCounter:
    def add(self, *_args, **_kwargs):
        pass


class FakeCache:
    def __init__(self, value):
        self.value = value

    def get(self, _key):
        return self.value


def test_exact_cache_response_carries_trace_and_cache_evidence(monkeypatch):
    trace_id = int("abcdef1234567890abcdef1234567890", 16)
    cache_value = json.dumps({
        "summary": "cached",
        "citations": [],
        "model_ver": "amazon.nova-pro-v1:0",
        "created_at": "2026-07-30T00:00:00+00:00",
    })
    monkeypatch.setattr(server, "tracer", FakeTracer(FakeSpan(trace_id)))
    monkeypatch.setattr(server, "get_bedrock_primary_client", lambda: object())
    monkeypatch.setattr(server, "apply_guardrail_input", lambda _client, value: (False, value))
    monkeypatch.setattr(server, "fetch_reviews_fingerprint", lambda _product_id: "fp")
    monkeypatch.setattr(server, "check_feature_flag", lambda name, default=False: name == "llmReviewsCacheEnabled")
    monkeypatch.setattr(server, "valkey_client", FakeCache(cache_value))
    monkeypatch.setattr(server, "product_review_svc_metrics", {"app_ai_assistant_counter": FakeCounter()})

    response = server.get_ai_assistant_response("product-1", "summary")

    assert response.trace_id == "abcdef1234567890abcdef1234567890"
    assert response.cache_status == "hit_exact"
    assert response.trace_steps[-1].status == "hit_exact"
    assert json.loads(response.trace_steps[-1].detail)["model_id"] == "amazon.nova-pro-v1:0"


def test_model_trace_step_redacts_internal_model_arn():
    step = server._model_trace_step(_response(), "arn:aws:bedrock:us-east-1:123456789012:application-inference-profile/internal", "ok", 10)
    detail = json.loads(step.detail)
    assert detail["model_id"] == "internal"
    assert "123456789012" not in step.detail


def test_gateway_metrics_cover_usage_latency_cost_and_outcome(monkeypatch):
    import llm_trace
    instruments = {name: MagicMock() for name in (
        "requests", "latency", "input_tokens", "output_tokens", "cost"
    )}
    for name, instrument in instruments.items():
        monkeypatch.setattr(llm_trace, f"gateway_{name}", instrument)
    llm_trace.record_gateway_metrics(
        "amazon.nova-lite-v1:0", "reviews_summary", "fallback",
        {"inputTokens": 200, "outputTokens": 100}, 0.05,
    )
    attrs = {"model_id": "amazon.nova-lite-v1:0", "task_type": "reviews_summary", "status": "fallback"}
    instruments["requests"].add.assert_called_once_with(1, attrs)
    instruments["latency"].record.assert_called_once_with(50.0, attrs)
    instruments["input_tokens"].add.assert_called_once_with(200, attrs)
    instruments["output_tokens"].add.assert_called_once_with(100, attrs)
    assert instruments["cost"].add.call_args.args[0] > 0

def test_gateway_metrics_redact_arn_and_never_break_serving(monkeypatch):
    import llm_trace
    requests = MagicMock()
    requests.add.side_effect = RuntimeError("exporter unavailable")
    monkeypatch.setattr(llm_trace, "gateway_requests", requests)

    llm_trace.record_gateway_metrics(
        "arn:aws:bedrock:us-east-1:123456789012:application-inference-profile/public-name",
        "reviews_summary", "ok", {}, 0.01,
    )

    attributes = requests.add.call_args.args[1]
    assert attributes["model_id"] == "public-name"
    assert "123456789012" not in str(attributes)
