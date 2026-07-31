import hashlib
import logging
import math
import os
import random
import time

from openfeature import api
from openfeature.contrib.provider.flagd import FlagdProvider
from openfeature.evaluation_context import EvaluationContext
from opentelemetry import metrics, trace

logger = logging.getLogger(__name__)
tracer = trace.get_tracer("model-router")
meter = metrics.get_meter("model-gateway")
route_counter = meter.create_counter(
    "llm.gateway.routes", unit="requests", description="Model gateway routing decisions"
)
route_latency = meter.create_histogram(
    "llm.gateway.route.latency", unit="ms", description="Model gateway routing latency"
)

def _record_route(started_at: float, model_id: str, task_type: str, outcome: str) -> str:
    public_model_id = model_id.rsplit("/", 1)[-1] if model_id.startswith("arn:") else model_id
    attributes = {"model_id": public_model_id, "task_type": task_type, "outcome": outcome}
    try:
        route_counter.add(1, attributes)
        route_latency.record((time.perf_counter() - started_at) * 1000, attributes)
    except Exception:
        logger.exception("Model route metrics failed")
    return model_id

_provider_set = False


def _ensure_provider():
    global _provider_set
    if not _provider_set:
        api.set_provider(FlagdProvider(
            host=os.environ.get("FLAGD_HOST", "flagd"),
            port=int(os.environ.get("FLAGD_PORT", "8013")),
        ))
        _provider_set = True


def check_feature_flag(flag_name: str, default: bool = False) -> bool:
    try:
        _ensure_provider()
        return api.get_client().get_boolean_value(flag_name, default)
    except Exception as exc:
        logger.warning("Feature flag %s unavailable: %s", flag_name, exc)
        return default


def _validated_routes(config):
    if not isinstance(config, dict) or not config:
        return None
    routes = []
    for model_id, weight in config.items():
        if not isinstance(model_id, str) or not model_id or not (
            model_id.startswith("amazon.") or model_id.startswith("arn:aws:bedrock:")
        ):
            return None
        if isinstance(weight, bool) or not isinstance(weight, (int, float)):
            return None
        numeric_weight = float(weight)
        if not math.isfinite(numeric_weight) or numeric_weight <= 0:
            return None
        routes.append((model_id, numeric_weight))
    return routes


def _sticky_choice(routes, routing_key: str):
    digest = hashlib.sha256(f"llm-model-gateway:v1:{routing_key}".encode()).digest()
    bucket = int.from_bytes(digest[:8], "big") / 2**64
    total = sum(weight for _, weight in routes)
    cursor = 0.0
    for model_id, weight in routes:
        cursor += weight / total
        if bucket < cursor:
            return model_id
    return routes[-1][0]


def get_routed_model(task_type: str, default_model: str, routing_key: str = "") -> str:
    """Select a model from the validated flagd traffic split."""
    started_at = time.perf_counter()
    with tracer.start_as_current_span("model_gateway.route") as span:
        span.set_attribute("task_type", task_type)
        try:
            _ensure_provider()
            anonymized_key = hashlib.sha256(routing_key.encode()).hexdigest() if routing_key else ""
            context = EvaluationContext(
                targeting_key=anonymized_key, attributes={"task_type": task_type}
            )
            config = api.get_client().get_object_value("llmModelRouting", {}, context)
            routes = _validated_routes(config)
            if not routes:
                span.set_attribute("routed_model", default_model)
                span.set_attribute("route.outcome", "fallback_invalid_config")
                return _record_route(started_at, default_model, task_type, "fallback_invalid_config")
            if routing_key:
                model_name = _sticky_choice(routes, routing_key)
            else:
                models, weights = zip(*routes)
                model_name = random.choices(list(models), weights=list(weights), k=1)[0]
            span.set_attribute("routed_model", model_name)
            span.set_attribute("route.outcome", "experiment")
            return _record_route(started_at, model_name, task_type, "experiment")
        except Exception as exc:
            logger.warning("Model Router error: %s. Falling back to %s", exc, default_model)
            span.set_attribute("routed_model", default_model)
            span.set_attribute("route.outcome", "fallback_error")
            return _record_route(started_at, default_model, task_type, "fallback_error")
