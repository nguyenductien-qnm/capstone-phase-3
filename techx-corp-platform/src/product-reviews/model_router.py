import logging
import hashlib
import math
import os
import random
import time

from openfeature import api
from opentelemetry import metrics, trace

logger = logging.getLogger(__name__)
tracer = trace.get_tracer("product-reviews-model-router")
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

_DEFAULT_MODEL = "amazon.nova-lite-v1:0"


def _valid_routes(config):
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
        value = float(weight)
        if not math.isfinite(value) or value <= 0:
            return None
        routes.append((model_id, value))
    return routes


class ModelRouter:
    def __init__(self):
        self.of_client = api.get_client()

    def get_main_model(self, routing_key: str = ""):
        default_model = os.environ.get("LLM_REVIEWS_MAIN_MODEL", os.environ.get("AWS_BEDROCK_MODEL", _DEFAULT_MODEL))
        task_type = "reviews_summary"
        started_at = time.perf_counter()
        with tracer.start_as_current_span("model_gateway.route") as span:
            span.set_attribute("task_type", task_type)
            try:
                routes = _valid_routes(self.of_client.get_object_value("llmReviewsModelRouting", {}))
                if not routes:
                    span.set_attribute("routed_model", default_model)
                    span.set_attribute("route.outcome", "fallback_invalid_config")
                    return _record_route(started_at, default_model, task_type, "fallback_invalid_config")
                if routing_key:
                    digest = hashlib.sha256(
                        f"reviews-model-gateway:v1:{routing_key}".encode()
                    ).digest()
                    bucket = int.from_bytes(digest[:8], "big") / 2**64
                    # Sort by model_id: reordering the flagd JSON must not change cohorts.
                    sorted_routes = sorted(routes, key=lambda r: r[0])
                    total = sum(weight for _, weight in sorted_routes)
                    cursor = 0.0
                    selected = sorted_routes[-1][0]
                    for model_id, weight in sorted_routes:
                        cursor += weight / total
                        if bucket < cursor:
                            selected = model_id
                            break
                else:
                    models, weights = zip(*routes)
                    selected = random.choices(list(models), weights=list(weights), k=1)[0]
                span.set_attribute("routed_model", selected)
                span.set_attribute("route.outcome", "experiment")
                return _record_route(started_at, selected, task_type, "experiment")
            except Exception as exc:
                logger.warning("Reviews model router unavailable: %s", exc)
                span.set_attribute("routed_model", default_model)
                span.set_attribute("route.outcome", "fallback_error")
                return _record_route(started_at, default_model, task_type, "fallback_error")
