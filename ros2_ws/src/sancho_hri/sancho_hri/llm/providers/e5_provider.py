from .hf_embedding_provider import HFEmbeddingProvider


class E5Provider(HFEmbeddingProvider):
    def __init__(self, models=None):
        super().__init__(models)
