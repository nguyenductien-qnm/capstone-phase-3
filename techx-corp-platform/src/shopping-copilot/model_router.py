import os
import logging
from openfeature import api
from openfeature.contrib.provider.flagd import FlagdProvider

logger = logging.getLogger(__name__)

_provider_set = False

def get_routed_model(task_type: str, default_model: str) -> str:
    """
    Model Gateway (ADR-010): fractional routing via OpenFeature/flagd.
    Returns the model ID to use.
    """
    global _provider_set
    if not _provider_set:
        api.set_provider(FlagdProvider(
            host=os.environ.get("FLAGD_HOST", "flagd"),
            port=int(os.environ.get("FLAGD_PORT", "8013"))
        ))
        _provider_set = True

    client = api.get_client()
    # For A/B testing, we expect the flag to return the model ID string.
    # If the flag is not set or flagd is down, it returns default_model.
    # The flag name is llmModelRouting.
    
    # We pass an evaluation context to differentiate routing by task_type
    context = {"task_type": task_type}
    try:
        routed_model = client.get_string_value("llmModelRouting", default_model, context)
        return routed_model
    except Exception as e:
        logger.warning(f"Model Router error: {e}. Falling back to {default_model}")
        return default_model
