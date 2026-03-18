from .intent_classifier import IntentClassifier

from ...log_manager import LogManager
from ...engines import EmbeddingEngine
from ...prompts.commands import COMMANDS, IntentExamplesEmbeddingRegistry

import numpy as np


class EmbeddingClassifier(IntentClassifier):

    SIMILARITY_THRESHOLD = 0.8

    def __init__(self, embedding_engine: EmbeddingEngine, provider: str = None, model: str = None):
        self.embedding_engine = embedding_engine
        self.provider = provider
        self.model = model

        self.examples = IntentExamplesEmbeddingRegistry.get_intent_examples()

    def classify(self, user_input, _):
        LogManager.info(f"User: {user_input}")
        
        user_embedding, provider_used, model_used, message, success = self.embedding_engine.embedding_request(
            user_input=user_input,
            **{"provider": self.provider, "model": self.model} if (self.provider and self.model) else {}
        )
        
        if not success:
            LogManager.error(f"Error in embedding request: {message}")
            return COMMANDS.UNKNOWN, {}, provider_used, model_used
        
        user_embedding = np.array(user_embedding)

        best_intent = COMMANDS.UNKNOWN
        best_similarity = -1.0

        for intent, examples in self.examples.items():
            for phrase, models in examples.items():
                if model_used in models:
                    example_embedding = np.array(models[model_used])
                    similarity = self.cosine_similarity(user_embedding, example_embedding)
                    if similarity > best_similarity:
                        best_similarity = similarity
                        best_intent = intent

        if best_similarity >= self.SIMILARITY_THRESHOLD and best_intent in list(COMMANDS):
            return best_intent, {}, provider_used, model_used
        else:
            LogManager.info(f"Embedding similarity too low ({best_similarity:.2f}), classified as UNKNOWN")
            return COMMANDS.UNKNOWN, {}, provider_used, model_used

    @staticmethod
    def cosine_similarity(a, b):
        return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-9)
