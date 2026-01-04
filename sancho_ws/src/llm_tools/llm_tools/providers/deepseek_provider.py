from .hf_emb_llm_provider import HFEmbLLMProvider
from ..models import PROVIDER


class DeepSeekProvider(HFEmbLLMProvider):
    def __init__(self, models=None):
        super().__init__(PROVIDER.DEEPSEEK, models)