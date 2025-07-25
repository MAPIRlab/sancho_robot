import os
import json

class IntentExamplesEmbeddingRegistry:
    _intent_embeddings = None

    @classmethod
    def get_intent_examples(cls):
        if cls._intent_embeddings is None:
            current_dir = os.path.dirname(__file__)
            path = os.path.join(current_dir, 'intent_embeddings.json')
            with open(path, 'r', encoding='utf-8') as f:
                cls._intent_embeddings = json.load(f)
        return cls._intent_embeddings
