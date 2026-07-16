import random
import os
from openfeature import api

class ModelRouter:
    def __init__(self):
        self.of_client = api.get_client()

    def get_main_model(self):
        config = self.of_client.get_object_value("llmModelRouting", {})
        
        if not config:
            return os.environ.get('LLM_REVIEWS_MAIN_MODEL', os.environ.get('AWS_BEDROCK_MODEL', 'amazon.nova-lite-v1:0'))
            
        models = list(config.keys())
        weights = list(config.values())
        
        if not models or sum(weights) == 0:
            return os.environ.get('LLM_REVIEWS_MAIN_MODEL', os.environ.get('AWS_BEDROCK_MODEL', 'amazon.nova-lite-v1:0'))
            
        return random.choices(models, weights=weights, k=1)[0]
