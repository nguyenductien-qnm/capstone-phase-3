import random
import os
from openfeature import api
from opentelemetry import trace

tracer = trace.get_tracer("product-reviews-model-router")

class ModelRouter:
    def __init__(self):
        self.of_client = api.get_client()

    def get_main_model(self):
        # ADR-004: reviews stays on Nova Lite (high volume/simple task).
        # Deliberately not the shared "llmModelRouting" flag copilot A/B-tests
        # Nova Pro on — that flag leaking into reviews sends real Pro-priced
        # traffic here, ~13x the Lite cost, contradicting ADR-004.
        with tracer.start_as_current_span("model_gateway.route") as span:
            config = self.of_client.get_object_value("llmReviewsModelRouting", {})
            
            if not config:
                default_model = os.environ.get('LLM_REVIEWS_MAIN_MODEL', os.environ.get('AWS_BEDROCK_MODEL', 'arn:aws:bedrock:us-east-1:804372444787:application-inference-profile/krbq2wsgp11t'))
                span.set_attribute("routed_model", default_model)
                return default_model
                
            models = list(config.keys())
            weights = list(config.values())
            
            if not models or sum(weights) == 0:
                default_model = os.environ.get('LLM_REVIEWS_MAIN_MODEL', os.environ.get('AWS_BEDROCK_MODEL', 'arn:aws:bedrock:us-east-1:804372444787:application-inference-profile/krbq2wsgp11t'))
                span.set_attribute("routed_model", default_model)
                return default_model
                
            model_name = random.choices(models, weights=weights, k=1)[0]
            span.set_attribute("routed_model", model_name)
            return model_name
