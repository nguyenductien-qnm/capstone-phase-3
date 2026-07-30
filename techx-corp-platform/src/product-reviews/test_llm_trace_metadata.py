import os

os.environ.setdefault("DB_CONNECTION_STRING", "host=test user=test password=test dbname=test")

import product_reviews_server as server


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
