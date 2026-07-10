import importlib.util
import pathlib
import pytest

# pytest wrapper, to future proof in case of 
# development of multiple test files.
# prevents the scenario of doing 
# python -m pytest ./file1
# python -m pytest ./file2
_spec = importlib.util.spec_from_file_location(
    "test_task_success_module",
    pathlib.Path(__file__).with_name("test_task_success.py"),
)
_test_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_test_mod)

scenarios = _test_mod.TASK_SUCCESS_SCENARIOS


def idfn(s):
    return s.get("id")


@pytest.mark.parametrize("scenario", scenarios, ids=idfn)
def test_task_success_scenario(scenario):
    """Each scenario must pass the evaluator.

    The evaluator will raise if imports or the mock agent fail, which is
    deliberate: CI should fail loudly when the agent or imports are broken.
    """
    tool_calls = _test_mod.extract_tool_calls_from_mock(scenario["user_input"])
    result = _test_mod.evaluate_scenario(scenario, tool_calls)
    assert result["passed"], f"Scenario {scenario['id']} failed: {result['details']}"
