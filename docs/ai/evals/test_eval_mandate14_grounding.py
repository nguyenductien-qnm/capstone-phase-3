import pytest
import eval_mandate14 as m


SOURCE = [{"username": "u1", "description": "Ống kính rõ nét", "score": "4.0"}]
RESPONSE = {
    "response": "Khách đánh giá ống kính rõ nét.",
    "citations": [{"reviewId": "u1", "snippet": "Ống kính rõ nét", "score": "4.0"}],
}


def test_review_faithfulness_checks_source_then_live_judge():
    called = []

    def judge(case):
        called.append(case)
        return {"label": "PASS", "rationale": "Supported by source"}

    passed, reason = m.validate_review_faithfulness("Review thế nào?", RESPONSE, SOURCE, judge=judge)
    assert passed
    assert called[0]["source_text"]
    assert "Live judge PASS" in reason


def test_review_faithfulness_rejects_fabricated_citation_before_judge():
    bad = {**RESPONSE, "citations": [{"reviewId": "u1", "snippet": "Pin 24 giờ", "score": "4.0"}]}
    passed, reason = m.validate_review_faithfulness("Review thế nào?", bad, SOURCE, judge=lambda _: (_ for _ in ()).throw(AssertionError()))
    assert not passed
    assert "does not match source" in reason


def test_hallucination_fails_even_when_tool_and_rail_would_pass():
    hallucinated = {
        **RESPONSE,
        "response": "Kính này có pin rất trâu, dùng liên tục 24 giờ.",
    }

    def judge(case):
        assert "pin rất trâu" in case["llm_output"]
        assert "Ống kính rõ nét" in case["source_text"]
        return {"label": "FAIL", "rationale": "Battery claim is absent from source"}

    passed, reason = m.validate_review_faithfulness(
        "Pin dùng được bao lâu?", hallucinated, SOURCE, judge=judge
    )
    assert not passed
    assert "ungrounded content" in reason


def test_extract_trace_tokens_falls_back_to_safe_ui_trace_metadata(monkeypatch):
    monkeypatch.setattr(m, "jaeger_client", None)
    data = {
        "traceSteps": [
            {"detail": '{"model_id":"amazon.nova-pro-v1:0","tokens_in":120,"tokens_out":30,"cost_usd":0.000192}'},
            {"detail": '{"tool_calls":["search_products"]}'},
            {"detail": '{"model_id":"amazon.nova-pro-v1:0","tokens_in":80,"tokens_out":20,"cost_usd":0.000128}'},
        ]
    }

    _, _, tokens_in, tokens_out, cost, _, _ = m.extract_trace_and_tokens(data)

    assert tokens_in == 200
    assert tokens_out == 50
    assert cost == pytest.approx(0.00032)
