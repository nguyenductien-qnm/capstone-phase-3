import os

os.environ["LLM_INJECTION_JUDGE"] = "false"
os.environ["ML_GUARD_URL"] = ""

import agent


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
        "stopReason": "end_turn",
        "usage": {"inputTokens": input_tokens, "outputTokens": output_tokens},
        "output": {"message": {"content": [{"text": "ok"}]}},
    }


def test_fallback_trace_uses_fallback_model_outcome_and_cost(monkeypatch):
    fallback_model = "amazon.nova-lite-v1:0"
    monkeypatch.setenv("LLM_COPILOT_FALLBACK_MODEL", fallback_model)
    monkeypatch.setattr(agent, "_current_trace_id", lambda: "trace-1")

    traces = []
    monkeypatch.setattr(agent, "record_trace", lambda _client, trace: traces.append(trace))
    monkeypatch.setattr(agent._executor, "submit", lambda fn, *args: fn(*args))

    result = agent.run_agent(
        FakeBedrock([RuntimeError("primary failed"), _response()]),
        "amazon.nova-pro-v1:0",
        [{"role": "user", "content": [{"text": "hi"}]}],
        "u1",
        valkey_client=object(),
        session_id="s1",
    )

    assert result.degraded is False
    assert traces[0]["model_id"] == fallback_model
    assert traces[0]["outcome"] == "fallback"
    assert traces[0]["cost_usd"] == 0.00000018


def test_failed_fallback_trace_has_zero_cost(monkeypatch):
    fallback_model = "amazon.nova-lite-v1:0"
    monkeypatch.setenv("LLM_COPILOT_FALLBACK_MODEL", fallback_model)
    monkeypatch.setattr(agent, "_current_trace_id", lambda: "trace-2")

    traces = []
    monkeypatch.setattr(agent, "record_trace", lambda _client, trace: traces.append(trace))
    monkeypatch.setattr(agent._executor, "submit", lambda fn, *args: fn(*args))

    result = agent.run_agent(
        FakeBedrock([RuntimeError("primary failed"), RuntimeError("fallback failed")]),
        "amazon.nova-pro-v1:0",
        [{"role": "user", "content": [{"text": "hi"}]}],
        "u1",
        valkey_client=object(),
        session_id="s1",
    )

    assert result.degraded is True
    assert traces[0]["model_id"] == fallback_model
    assert traces[0]["outcome"] == "error"
    assert traces[0]["cost_usd"] == 0
