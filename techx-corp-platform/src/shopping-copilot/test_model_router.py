import math
import random
from unittest.mock import MagicMock, patch

import model_router


def _client(config):
    client = MagicMock()
    client.get_object_value.return_value = config
    return client


def test_routes_using_valid_weights_and_context():
    client = _client({"amazon.nova-lite-v1:0": 80, "amazon.nova-pro-v1:0": 20})
    with patch.object(model_router, "_ensure_provider"), patch.object(model_router.api, "get_client", return_value=client), patch.object(model_router.random, "choices", return_value=["amazon.nova-pro-v1:0"]) as choices:
        selected = model_router.get_routed_model("copilot", "amazon.nova-lite-v1:0")
    assert selected == "amazon.nova-pro-v1:0"
    assert choices.call_args.kwargs["weights"] == [80.0, 20.0]
    assert client.get_object_value.call_args.args[2].attributes["task_type"] == "copilot"


def test_invalid_config_falls_back_without_random_selection():
    configs = [[], {"amazon.nova-lite-v1:0": -1}, {"amazon.nova-lite-v1:0": math.nan}, {"amazon.nova-lite-v1:0": "heavy"}, {"": 100}, {"not-a-bedrock-model": 100}]
    for config in configs:
        client = _client(config)
        with patch.object(model_router, "_ensure_provider"), patch.object(model_router.api, "get_client", return_value=client), patch.object(model_router.random, "choices") as choices:
            assert model_router.get_routed_model("copilot", "amazon.nova-lite-v1:0") == "amazon.nova-lite-v1:0"
            choices.assert_not_called()


def test_flag_error_falls_back_and_marks_route_span():
    client = MagicMock()
    client.get_object_value.side_effect = RuntimeError("flagd unavailable")
    span, scope = MagicMock(), MagicMock()
    scope.__enter__.return_value, scope.__exit__.return_value = span, False
    with patch.object(model_router, "_ensure_provider"), patch.object(model_router.api, "get_client", return_value=client), patch.object(model_router.tracer, "start_as_current_span", return_value=scope):
        assert model_router.get_routed_model("copilot", "amazon.nova-lite-v1:0") == "amazon.nova-lite-v1:0"
    span.set_attribute.assert_any_call("route.outcome", "fallback_error")

def test_configured_split_is_stable_at_evaluation_volume():
    routes = model_router._validated_routes(
        {"amazon.nova-lite-v1:0": 80, "amazon.nova-pro-v1:0": 20}
    )
    models, weights = zip(*routes)
    rng = random.Random(20260731)
    selected = rng.choices(models, weights=weights, k=10_000)
    pro_ratio = selected.count("amazon.nova-pro-v1:0") / len(selected)
    assert 0.19 <= pro_ratio <= 0.21

def test_route_emits_gateway_metrics():
    client = _client({"amazon.nova-lite-v1:0": 100})
    counter, latency = MagicMock(), MagicMock()
    with patch.object(model_router, "_ensure_provider"), \
            patch.object(model_router.api, "get_client", return_value=client), \
            patch.object(model_router.random, "choices", return_value=["amazon.nova-lite-v1:0"]), \
            patch.object(model_router, "route_counter", counter), \
            patch.object(model_router, "route_latency", latency):
        model_router.get_routed_model("copilot", "amazon.nova-lite-v1:0")
    attrs = {"model_id": "amazon.nova-lite-v1:0", "task_type": "copilot", "outcome": "experiment"}
    counter.add.assert_called_once_with(1, attrs)
    assert latency.record.call_args.args[1] == attrs

def test_routing_key_is_sticky_and_forwarded_without_pii():
    client = _client({"amazon.nova-lite-v1:0": 80, "amazon.nova-pro-v1:0": 20})
    with patch.object(model_router, "_ensure_provider"), patch.object(
        model_router.api, "get_client", return_value=client
    ), patch.object(model_router.random, "choices") as choices:
        first = model_router.get_routed_model("copilot", "amazon.nova-lite-v1:0", "user-42")
        second = model_router.get_routed_model("copilot", "amazon.nova-lite-v1:0", "user-42")

    assert first == second
    choices.assert_not_called()
    context = client.get_object_value.call_args.args[2]
    assert context.targeting_key != "user-42"
    assert len(context.targeting_key) == 64
