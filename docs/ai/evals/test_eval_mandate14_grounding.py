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
