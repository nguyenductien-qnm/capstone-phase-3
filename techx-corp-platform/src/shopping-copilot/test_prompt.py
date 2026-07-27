import agent


def test_prompt_requires_confirmation_gate_and_real_catalog_lookup():
    prompt = agent.SYSTEM_PROMPT

    assert "CONFIRMATION GATE" in prompt
    assert "Bắt buộc phải gọi tool add_item_to_cart" in prompt
    assert "Vui lòng xác nhận để thực hiện" in prompt
    assert "PHẢI gọi tool search_products" in prompt
