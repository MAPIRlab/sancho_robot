import gc
import json
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

from .base_provider import BaseProvider
from ..prompt_formatters import HFChatTemplateFormatter


class HFLLMProvider(BaseProvider):
    def __init__(self, models=None, api_key=None, model_formatters=None):
        self.api_key = api_key
        self.model_formatters = model_formatters
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

        self.models = {}
        self.tokenizers = {}
        self.formatters = {}

        if models:
            self.load(models)

    def embedding(self, *args, **kwargs):
        raise NotImplementedError("This provider does not support embeddings.")

    def prompt(self, model, prompt_system, messages_json, user_input, parameters_json):
        if not model:
            model = list(self.models.keys())[0]

        tokenizer = self.tokenizers[model]
        formatter = self.formatters[model]
        model_obj = self.models[model]

        model_inputs = formatter.format(prompt_system, messages_json, user_input).to(self.device)
        parameters = json.loads(parameters_json) if parameters_json else {}
        final_parameters = {
            "temperature": parameters.get("temperature", 0.0),
            "max_new_tokens": parameters.get("max_tokens", 60),
            "do_sample": parameters.get("temperature", 0.0) > 0.0
        }

        generated_ids = model_obj.generate(model_inputs, **final_parameters)
        new_tokens = generated_ids[0][model_inputs.shape[1]:]
        response = tokenizer.decode(new_tokens, skip_special_tokens=True)

        return response, model

    def load(self, models):
        for model_enum in models:
            tokenizer = AutoTokenizer.from_pretrained(model_enum, token=self.api_key)
            model = AutoModelForCausalLM.from_pretrained(
                model_enum,
                torch_dtype=torch.float16 if torch.cuda.is_available() else torch.float32,
                device_map="auto" if torch.cuda.is_available() else None,
                token=self.api_key
            )

            self.models[model_enum] = model
            self.tokenizers[model_enum] = tokenizer
            self.formatters[model_enum] = (self.model_formatters or {}).get(model_enum, HFChatTemplateFormatter)(tokenizer)

    def unload(self, models=None):
        if not models:
            models = self.get_active_models()

        for model_enum in models:
            del self.models[model_enum]
            del self.tokenizers[model_enum]
            del self.formatters[model_enum]

        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()

    def get_active_models(self):
        return list(self.models.keys())