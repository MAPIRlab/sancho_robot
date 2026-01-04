from .hf_llm_provider import HFLLMProvider


class GemmaProvider(HFLLMProvider):
    def __init__(self, models=None, api_key=None):
        super().__init__(models, api_key)