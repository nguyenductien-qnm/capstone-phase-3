"""Self-check for the Shopping Copilot servicer (TF1-59).

No AWS, no live gRPC. A scripted fake Bedrock client drives the agent loop and
``tools`` is monkeypatched, so this exercises the logic that must not break:

  1. Confirmation gate (the one safety-critical path): add_item_to_cart is
     PREPARED, never executed, until the user re-sends the token.
  2. Token is single-use and the real CartService.AddItem runs only in phase 2.
  3. Read-tool routing dispatches to the right tool and records an audit entry.
  4. Max-loop hard limit bounds tool calls per turn.
  5. Bedrock failure degrades gracefully instead of crashing.

Run: ``python test_copilot.py``
"""

import os
os.environ["LLM_INJECTION_JUDGE"] = "false"

import copilot_server as srv
import agent
import tools


class FakeBedrock:
    """converse() returns the next scripted response each call."""
    def __init__(self, scripted):
        self._scripted = list(scripted)

    def converse(self, **kwargs):
        if not self._scripted:
            raise AssertionError("FakeBedrock ran out of scripted responses")
        item = self._scripted.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


def _tool_use(name, inp):
    return {"stopReason": "tool_use",
            "output": {"message": {"content": [{"toolUse": {"name": name, "input": inp, "toolUseId": "t1"}}]}}}


def _end(text):
    return {"stopReason": "end_turn", "output": {"message": {"content": [{"text": text}]}}}


class _Req:
    def __init__(self, user_id="u1", question="", session_id="s1", confirmation_token=""):
        self.user_id = user_id
        self.question = question
        self.session_id = session_id
        self.confirmation_token = confirmation_token


def test_confirmation_gate_two_phase():
    executed = []
    orig = tools.execute_add_item
    tools.execute_add_item = lambda uid, pid, qty: executed.append((uid, pid, qty)) or '{"status":"success"}'
    try:
        bedrock = FakeBedrock([
            # LLM_INJECTION_JUDGE=false (set before import above) disables the T2
            # injection judge, so run_agent's converse loop is the only consumer of
            # scripted items — no judge placeholder needed (stale "NO" item removed
            # 18/07: with the judge off it was consumed as the final answer and the
            # confirmation token was never produced).
            _tool_use("add_item_to_cart", {"product_id": "OLJCESPC7Z", "quantity": 2}),
            _end("Tôi đã chuẩn bị thêm vào giỏ. Vui lòng xác nhận."),
        ])
        servicer = srv.ShoppingCopilotServicer(bedrock)

        # Phase 1: prepare — must NOT execute the write.
        r1 = servicer.ChatWithCopilot(_Req(question="thêm OLJCESPC7Z"), None)
        assert executed == [], "write executed before confirmation!"
        token = r1.pending_confirmation.confirmation_token
        assert token, "no confirmation token returned"
        assert r1.pending_confirmation.tool_name == "add_item_to_cart"

        # Phase 2: confirm — now the real AddItem runs, exactly once, right args.
        r2 = servicer.ChatWithCopilot(_Req(confirmation_token=token), None)
        assert executed == [("u1", "OLJCESPC7Z", 2)], f"bad execution: {executed}"
        assert any(a.tool_name == "add_item_to_cart" and a.succeeded for a in r2.actions_taken)

        # Token is single-use.
        r3 = servicer.ChatWithCopilot(_Req(confirmation_token=token), None)
        assert "hết hạn" in r3.response or "không hợp lệ" in r3.response
        assert executed == [("u1", "OLJCESPC7Z", 2)], "token reused!"
    finally:
        tools.execute_add_item = orig


def test_read_tool_routing_and_audit():
    orig = tools.get_product_reviews
    seen = []
    tools.get_product_reviews = lambda pid: seen.append(pid) or (
        '{"status":"ok","review_count":1,"average_score":4.8,"summary":"good",'
        '"citations":[{"review_id":"alice","snippet":"good","score":"4.8"}]}'
    )
    try:
        bedrock = FakeBedrock([
            _tool_use("get_product_reviews", {"product_id": "L9ECAV7KIM"}),
            _end("Điểm trung bình 4.8, theo đánh giá thật của khách."),
        ])
        res = agent.run_agent(bedrock, "m", [{"role": "user", "content": [{"text": "review?"}]}], "u1")
        assert seen == ["L9ECAV7KIM"], f"tool not routed: {seen}"
        assert res.pending is None
        assert any(a.tool_name == "get_product_reviews" and a.succeeded for a in res.actions_taken)
        # Phase 5: citations collected from the tool result must reach AgentResult
        # (unless the output-grounding guardrail blocked the answer).
        assert res.citations == [{"review_id": "alice", "snippet": "good", "score": "4.8"}], res.citations
    finally:
        tools.get_product_reviews = orig


def test_max_loop_limit():
    # Always ask for another tool -> must stop at MAX_TOOL_CALLS, not loop forever.
    scripted = [_tool_use("get_cart", {}) for _ in range(agent.MAX_TOOL_CALLS + 3)]
    orig = tools.get_cart
    tools.get_cart = lambda uid: '{"status":"ok","items":[]}'
    try:
        res = agent.run_agent(FakeBedrock(scripted), "m", [{"role": "user", "content": [{"text": "x"}]}], "u1")
        assert len(res.actions_taken) <= agent.MAX_TOOL_CALLS
        assert "giới hạn" in res.text
    finally:
        tools.get_cart = orig


def test_degraded_on_bedrock_failure():
    res = agent.run_agent(FakeBedrock([RuntimeError("boom")]), "m",
                          [{"role": "user", "content": [{"text": "hi"}]}], "u1")
    assert res.degraded is True
    assert res.text and "trợ lý" in res.text.lower()



def test_thinking_tags_are_stripped():
    res = agent.run_agent(FakeBedrock([_end("<thinking>hidden</thinking> Visible answer")]), "m",
                          [{"role": "user", "content": [{"text": "hi"}]}], "u1")
    assert "thinking" not in res.text.lower()
    assert "hidden" not in res.text
    assert res.text == "Visible answer"


def test_reasoning_in_trace_steps():
    import json
    orig = tools.get_cart
    tools.get_cart = lambda uid: '{"status":"ok","items":[]}'
    try:
        res = agent.run_agent(FakeBedrock([
            {"stopReason": "tool_use",
             "output": {"message": {"content": [
                 {"text": "<thinking>need to check cart</thinking>\\nChecking cart now."},
                 {"toolUse": {"name": "get_cart", "input": {}, "toolUseId": "t1"}}
             ]}}},
            _end("Đã kiểm tra giỏ hàng xong.")
        ]), "m", [{"role": "user", "content": [{"text": "kiểm tra giỏ hàng"}]}], "u1")
        
        assert len(res.trace_steps) >= 1
        detail = json.loads(res.trace_steps[0]["detail"])
        assert "reasoning" in detail
        assert "Checking cart now." in detail["reasoning"]
    finally:
        tools.get_cart = orig


if __name__ == "__main__":
    test_confirmation_gate_two_phase()
    test_read_tool_routing_and_audit()
    test_max_loop_limit()
    test_degraded_on_bedrock_failure()
    test_thinking_tags_are_stripped()
    test_reasoning_in_trace_steps()

    print("OK — all shopping-copilot self-checks passed")
