"""
pytest_wrapper_test_task_success.py — Pytest wrapper for task-success eval
==========================================================================
JIRA    : TF-64

Two test modes:
  1. Real agent (Bedrock) — runs if AWS credentials are available
  2. Mock agent (legacy) — always runs as sanity check

Run:
  python -m pytest docs/ai/evals/pytest_wrapper_test_task_success.py -v
  python -m pytest docs/ai/evals/pytest_wrapper_test_task_success.py -v -k "real"
  python -m pytest docs/ai/evals/pytest_wrapper_test_task_success.py -v -k "mock"
"""

import importlib.util
import json
import os
import pathlib
import pytest

_SCRIPT_DIR = pathlib.Path(__file__).parent

# ─────────────────────────────────────────────
# Load modules dynamically (avoid Streamlit import issues)
# ─────────────────────────────────────────────

# Load legacy mock-based test module
_spec_mock = importlib.util.spec_from_file_location(
    "test_task_success_module",
    _SCRIPT_DIR / "test_task_success.py",
)
_test_mock_mod = importlib.util.module_from_spec(_spec_mock)
_spec_mock.loader.exec_module(_test_mock_mod)

# Load real agent eval module
_spec_real = importlib.util.spec_from_file_location(
    "test_task_success_real_module",
    _SCRIPT_DIR / "test_task_success_real.py",
)
_test_real_mod = importlib.util.module_from_spec(_spec_real)
_spec_real.loader.exec_module(_test_real_mod)

# Load agent adapter
_spec_adapter = importlib.util.spec_from_file_location(
    "agent_adapter_module",
    _SCRIPT_DIR / "agent_adapter.py",
)
_adapter_mod = importlib.util.module_from_spec(_spec_adapter)
_spec_adapter.loader.exec_module(_adapter_mod)

# Load scenarios
mock_scenarios = _test_mock_mod.TASK_SUCCESS_SCENARIOS
real_scenarios = _test_real_mod.load_scenarios(
    str(_SCRIPT_DIR / "golden_agent_tasks.json")
)

# Check if Bedrock credentials are available
_has_credentials = _adapter_mod.check_bedrock_credentials()


# ─────────────────────────────────────────────
# Legacy mock tests (backward compatibility)
# ─────────────────────────────────────────────
def mock_idfn(s):
    return f"mock-{s.get('id')}"


@pytest.mark.parametrize("scenario", mock_scenarios, ids=mock_idfn)
def test_mock_task_success(scenario):
    """[LEGACY/MOCK] Each scenario must pass the mock evaluator.

    DEPRECATED: This tests the keyword matcher, not the real agent.
    Kept for backward compatibility / CI sanity check.
    """
    tool_calls = _test_mock_mod.extract_tool_calls_from_mock(scenario["user_input"])
    result = _test_mock_mod.evaluate_scenario(scenario, tool_calls)
    assert result["passed"], f"Scenario {scenario['id']} failed: {result['details']}"


# ─────────────────────────────────────────────
# Real agent tests (Bedrock)
# ─────────────────────────────────────────────
def real_idfn(s):
    return f"real-{s.get('id')}"


@pytest.mark.skipif(
    not _has_credentials,
    reason="AWS Bedrock credentials not available — skipping real agent tests"
)
@pytest.mark.parametrize("scenario", real_scenarios, ids=real_idfn)
def test_real_agent_task_success(scenario):
    """[REAL AGENT] Each scenario evaluated against Bedrock Converse API.

    This is the TRUE eval — tests the actual LLM agent, not a keyword matcher.
    Requires valid AWS credentials with Bedrock access.
    """
    agent_result = _adapter_mod.run_agent(
        user_input=scenario["user_input"],
        model_id="amazon.nova-pro-v1:0",
        region="us-east-1",
    )

    eval_result = _test_real_mod.evaluate_scenario(scenario, agent_result)

    # Build assertion message
    details = eval_result["details"]
    tc_names = [tc.tool_name for tc in agent_result.tool_calls]
    msg = (
        f"Scenario {scenario['id']} failed.\n"
        f"  Input: \"{scenario['user_input']}\"\n"
        f"  Tools called: {tc_names}\n"
        f"  Details: {details}\n"
        f"  Response: {agent_result.final_response[:200]}"
    )
    assert eval_result["passed"], msg
