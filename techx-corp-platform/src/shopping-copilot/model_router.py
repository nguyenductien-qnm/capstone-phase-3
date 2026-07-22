import os
import logging
import random
from openfeature import api
from openfeature.contrib.provider.flagd import FlagdProvider
from openfeature.evaluation_context import EvaluationContext
from opentelemetry import trace

logger = logging.getLogger(__name__)
tracer = trace.get_tracer("model-router")

_provider_set = False


def _ensure_provider():
    global _provider_set
    if not _provider_set:
        api.set_provider(FlagdProvider(
            host=os.environ.get("FLAGD_HOST", "flagd"),
            port=int(os.environ.get("FLAGD_PORT", "8013"))
        ))
        _provider_set = True


def check_feature_flag(flag_name: str, default: bool = False) -> bool:
    """Boolean flag check via flagd — mirrors product-reviews' check_feature_flag()."""
    _ensure_provider()
    return api.get_client().get_boolean_value(flag_name, default)


def get_routed_model(task_type: str, default_model: str) -> str:
    """
    Model Gateway (ADR-010): fractional routing via OpenFeature/flagd.
    Returns the model ID to use.
    """
    with tracer.start_as_current_span("model_gateway.route") as span:
        span.set_attribute("task_type", task_type)
        _ensure_provider()
        client = api.get_client()
        # For A/B testing, we expect the flag to return the model ID string.
        # If the flag is not set or flagd is down, it returns default_model.
        # The flag name is llmModelRouting.
        
        # We pass an evaluation context to differentiate routing by task_type
        context = EvaluationContext(attributes={"task_type": task_type})
        try:
            config = client.get_object_value("llmModelRouting", {}, context)
            if not config:
                span.set_attribute("routed_model", default_model)
                return default_model
                
            models = list(config.keys())
            weights = list(config.values())
            
            if not models or sum(weights) == 0:
                span.set_attribute("routed_model", default_model)
                return default_model
                
            model_name = random.choices(models, weights=weights, k=1)[0]
            span.set_attribute("routed_model", model_name)
            return model_name
        except Exception as e:
            logger.warning(f"Model Router error: {e}. Falling back to {default_model}")
            span.set_attribute("routed_model", default_model)
            return default_model
