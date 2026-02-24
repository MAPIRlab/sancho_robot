from .hf_embedding_provider import HFEmbeddingProvider


class BAAIProvider(HFEmbeddingProvider):
    def __init__(self, models=None):
        super().__init__(models)
