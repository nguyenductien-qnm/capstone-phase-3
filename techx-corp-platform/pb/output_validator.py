"""Output validator for Bedrock model responses (MANDATE-25).

ponytail: validate toolUse blocks have required fields, block garbage args.
Upgrade path: full JSON Schema validation against expected tool input schemas.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def validate_tool_calls(response_content: list[dict]) -> tuple[bool, str]:
    """Check toolUse blocks in Bedrock Converse response for validity.

    Returns (is_valid, error_message). Reject if:
    - toolUse missing required fields (name, toolUseId, input)
    - toolUse input is not a dict
    - toolUse name is empty string
    """
    for block in response_content:
        if "toolUse" not in block:
            continue
        tu = block["toolUse"]
        if not isinstance(tu, dict):
            return False, f"toolUse is not dict: {type(tu).__name__}"
        for field in ("name", "toolUseId", "input"):
            if field not in tu:
                return False, f"toolUse missing required field: {field}"
        if not tu["name"] or not isinstance(tu["name"], str):
            return False, f"toolUse name is empty or not string"
        if not isinstance(tu["input"], dict):
            return False, f"toolUse input is not dict: {type(tu['input']).__name__}"
    return True, ""


def validate_text_response(response_content: list[dict]) -> tuple[bool, str]:
    """Check text blocks in response are well-formed."""
    for block in response_content:
        if "text" in block:
            if not isinstance(block.get("text"), str):
                return False, "text block is not string"
    return True, ""
