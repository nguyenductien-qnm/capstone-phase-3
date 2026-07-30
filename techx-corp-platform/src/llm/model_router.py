import random
from openfeature import api

class ModelRouter:
    def __init__(self):
        self.of_client = api.get_client()

    def get_main_model(self, default_model):
        config = self.of_client.get_object_value("llmModelRouting", {})
        
        if not config:
            return default_model
            
        models = list(config.keys())
        weights = list(config.values())
        
        if not models or sum(weights) == 0:
            return default_model
            
        return random.choices(models, weights=weights, k=1)[0]
