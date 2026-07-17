import random
import os
from openfeature import api

class ModelRouter:
    def __init__(self):
        self.of_client = api.get_client()

    def get_main_model(self):
        # ADR-004: reviews stays on Nova Lite (high volume/simple task).
        # Deliberately not the shared "llmModelRouting" flag copilot A/B-tests
        # Nova Pro on — that flag leaking into reviews sends real Pro-priced
        # traffic here, ~13x the Lite cost, contradicting ADR-004.
        config = self.of_client.get_object_value("llmReviewsModelRouting", {})
        
        if not config:
            return os.environ.get('LLM_REVIEWS_MAIN_MODEL', os.environ.get('AWS_BEDROCK_MODEL', 'arn:aws:bedrock:us-east-1:804372444787:application-inference-profile/krbq2wsgp11t'))
            
        models = list(config.keys())
        weights = list(config.values())
        
        if not models or sum(weights) == 0:
            return os.environ.get('LLM_REVIEWS_MAIN_MODEL', os.environ.get('AWS_BEDROCK_MODEL', 'arn:aws:bedrock:us-east-1:804372444787:application-inference-profile/krbq2wsgp11t'))
            
        return random.choices(models, weights=weights, k=1)[0]
