import agent


def test_prompt_requires_confirmation_gate_and_real_catalog_lookup():
    prompt = agent.SYSTEM_PROMPT

    assert "CONFIRMATION GATE" in prompt
    assert "Call `add_item_to_cart`" in prompt
    assert "Please confirm to continue" in prompt
    assert "MUST call `search_products`" in prompt


def test_prompt_and_tool_guidance_are_english_primary_and_memory_aware():
    assert "Known customer preferences" in agent.SYSTEM_PROMPT
    guidance = " ".join(tool["toolSpec"]["description"] for tool in agent.TOOLS_DEFINITION)
    assert "Required catalog search" in guidance
    assert "TÌM KIẾM" not in guidance
    assert "khách" not in guidance.lower()
