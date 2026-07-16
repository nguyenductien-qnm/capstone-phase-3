import os
import sys

# Mock flagd
from unittest.mock import patch, MagicMock

# Create a mock openfeature client
mock_client = MagicMock()
def mock_get_object_value(flag_name, default_val):
    if flag_name == "llmModelRouting":
        return {
            "amazon.nova-pro-v1:0": 50,
            "techx-llm": 50
        }
    return default_val
mock_client.get_object_value = mock_get_object_value

with patch("model_router.api.get_client", return_value=mock_client):
    from model_router import ModelRouter
    router = ModelRouter()
    
    counts = {"amazon.nova-pro-v1:0": 0, "techx-llm": 0}
    for _ in range(100):
        model = router.get_main_model("amazon.nova-pro-v1:0")
        counts[model] = counts.get(model, 0) + 1
        
    print(f"Routing results for 100 iterations: {counts}")
    if counts["amazon.nova-pro-v1:0"] > 30 and counts["techx-llm"] > 30:
        print("✅ PASSED: A/B routing is distributing traffic.")
    else:
        print("❌ FAILED: Distribution is not even.")
        sys.exit(1)
