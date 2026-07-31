import math
from unittest.mock import MagicMock, patch
from model_router import ModelRouter


def test_reviews_use_isolated_flag_and_valid_route(monkeypatch):
    monkeypatch.delenv("LLM_REVIEWS_MAIN_MODEL", raising=False)
    client = MagicMock(); client.get_object_value.return_value = {"amazon.nova-lite-v1:0": 100}
    with patch("model_router.api.get_client", return_value=client), patch("model_router.random.choices", return_value=["amazon.nova-lite-v1:0"]):
        assert ModelRouter().get_main_model() == "amazon.nova-lite-v1:0"
    client.get_object_value.assert_called_once_with("llmReviewsModelRouting", {})


def test_reviews_fall_back_for_invalid_or_failed_flag(monkeypatch):
    monkeypatch.setenv("LLM_REVIEWS_MAIN_MODEL", "amazon.nova-lite-v1:0")
    for config in ({"amazon.nova-pro-v1:0": -1}, {"amazon.nova-pro-v1:0": math.inf}, {"bad-model": 100}):
        client = MagicMock(); client.get_object_value.return_value = config
        with patch("model_router.api.get_client", return_value=client), patch("model_router.random.choices") as choices:
            assert ModelRouter().get_main_model() == "amazon.nova-lite-v1:0"
            choices.assert_not_called()
    client = MagicMock(); client.get_object_value.side_effect = RuntimeError("flagd unavailable")
    with patch("model_router.api.get_client", return_value=client):
        assert ModelRouter().get_main_model() == "amazon.nova-lite-v1:0"


def test_reviews_route_emits_gateway_metrics(monkeypatch):
    monkeypatch.delenv("LLM_REVIEWS_MAIN_MODEL", raising=False)
    client = MagicMock(); client.get_object_value.return_value = {"amazon.nova-lite-v1:0": 100}
    counter, latency = MagicMock(), MagicMock()
    with patch("model_router.api.get_client", return_value=client), \
            patch("model_router.random.choices", return_value=["amazon.nova-lite-v1:0"]), \
            patch("model_router.route_counter", counter), patch("model_router.route_latency", latency):
        ModelRouter().get_main_model()
    attrs = {"model_id": "amazon.nova-lite-v1:0", "task_type": "reviews_summary", "outcome": "experiment"}
    counter.add.assert_called_once_with(1, attrs)
    assert latency.record.call_args.args[1] == attrs
