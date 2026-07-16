# Self-check: reviews must read its own routing flag, never copilot's shared
# llmModelRouting A/B flag (that leak sent 20% of review summaries to Nova
# Pro, ~13x the Lite cost, contradicting ADR-004). Run:
#   python3 src/product-reviews/test_model_router.py
from unittest.mock import MagicMock, patch

from model_router import ModelRouter


def main():
    with patch("model_router.api") as mock_api:
        client = MagicMock()
        mock_api.get_client.return_value = client

        # Simulate flagd still serving the old shared flag with Nova Pro in
        # it, and nothing registered yet under the new reviews-only flag.
        def get_object_value(flag_name, default):
            if flag_name == "llmReviewsModelRouting":
                return {}
            if flag_name == "llmModelRouting":
                return {"amazon.nova-lite-v1:0": 80, "amazon.nova-pro-v1:0": 20}
            return default

        client.get_object_value.side_effect = get_object_value

        router = ModelRouter()
        model = router.get_main_model()

        client.get_object_value.assert_called_once_with("llmReviewsModelRouting", {})
        assert model != "amazon.nova-pro-v1:0", (
            "reviews router must never resolve to Nova Pro via the shared "
            "copilot flag"
        )

    print("model_router self-check: OK (2 assertions)")


if __name__ == "__main__":
    main()
