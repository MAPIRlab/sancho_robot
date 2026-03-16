from .hf_llm_provider import HFLLMProvider


class YIProvider(HFLLMProvider):
    def __init__(self, models=None):
        super().__init__(models)