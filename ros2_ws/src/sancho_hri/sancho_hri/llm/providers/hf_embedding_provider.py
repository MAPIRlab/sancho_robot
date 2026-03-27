import gc
import torch

from sentence_transformers import SentenceTransformer

from .base_provider import BaseProvider


class HFEmbeddingProvider(BaseProvider):
    def __init__(self, models=None, api_key=None):
        self.api_key = api_key
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

        self.models = {}
        
        if models:
            self.load(models)

    def embedding(self, user_input, model):
        if not model:
            model = list(self.models.keys())[0]
        
        return self.models[model].encode([user_input])[0].tolist(), model

    def prompt(self, *args, **kwargs):
        raise NotImplementedError("This provider does not support prompts.")

    def load(self, models):
        for model_enum in models:
            self.models[model_enum] = SentenceTransformer(model_enum, use_auth_token=self.api_key, device=self.device)

    def unload(self, models=None):
        if not models:
            models = self.get_active_models()

        for model_enum in models:
            del self.models[model_enum]

        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()

    def get_active_models(self):
        return list(self.models.keys())