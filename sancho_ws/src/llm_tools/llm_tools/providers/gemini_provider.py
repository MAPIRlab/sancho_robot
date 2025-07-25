import json
import google.generativeai as genai

from .api_provider import APIProvider
from ..prompt_formatters import GeminiFormatter

from ..models import MODELS


class GeminiProvider(APIProvider):
    def __init__(self, api_key):
        genai.configure(api_key=api_key)

        self.client = {
            MODELS.LLM.GEMINI.GEMINI_1_5_FLASH: genai.GenerativeModel(MODELS.LLM.GEMINI.GEMINI_1_5_FLASH)
        }
        self.formatter = GeminiFormatter()

    def embedding(self, *args, **kwargs):
        raise NotImplementedError("This provider does not support embeddings.")

    def prompt(self, model, prompt_system, messages_json, user_input, parameters_json):
        if not model:
            model = list(self.client.keys())[0]

        messages = self.formatter.format(prompt_system, messages_json, user_input)
        chat = self.client[model].start_chat(history=messages)

        parameters = json.loads(parameters_json) if parameters_json else {}
        final_parameters = {
            "temperature": parameters.get("temperature", 0.0),
            "max_output_tokens": parameters.get("max_tokens", 60)
        }

        response = chat.send_message(messages[-1]["parts"][0], generation_config=final_parameters)

        return response.text.strip(), model

    def get_active_models(self):
        return list(self.client.keys())