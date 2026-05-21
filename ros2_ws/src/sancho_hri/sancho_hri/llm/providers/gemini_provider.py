import os
import json
import google.generativeai as genai
from google.generativeai.types import HarmCategory, HarmBlockThreshold

from .api_provider import APIProvider
from ..prompt_formatters import GeminiFormatter

from ..models import MODELS


class GeminiProvider(APIProvider):
    def __init__(self, api_key=None):
        if api_key is None:
            api_key = os.environ.get("GEMINI_API_KEY")
        
        if not api_key:
            raise ValueError("Gemini API key not found. Please provide it or set GEMINI_API_KEY env var.")

        genai.configure(api_key=api_key)

        self.client = {
            MODELS.LLM.GEMINI.GEMINI_FLASH_LATEST: genai.GenerativeModel(MODELS.LLM.GEMINI.GEMINI_FLASH_LATEST),
            MODELS.LLM.GEMINI.GEMINI_PRO_LATEST: genai.GenerativeModel(MODELS.LLM.GEMINI.GEMINI_PRO_LATEST),
            MODELS.LLM.GEMINI.GEMINI_2_5_FLASH: genai.GenerativeModel(MODELS.LLM.GEMINI.GEMINI_2_5_FLASH),
            MODELS.LLM.GEMINI.GEMINI_2_5_PRO: genai.GenerativeModel(MODELS.LLM.GEMINI.GEMINI_2_5_PRO)
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
            "max_output_tokens": parameters.get("max_tokens", 256)
        }

        safety_settings = {
            HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
            HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
            HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
            HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
        }

        response = chat.send_message(
            messages[-1]["parts"][0], 
            generation_config=final_parameters,
            safety_settings=safety_settings
        )

        try:
            return response.text.strip(), model
        except Exception:
            # Handle cases where response is blocked or empty
            if response.candidates:
                reason = response.candidates[0].finish_reason
                return f"[Blocked by safety filters. Reason: {reason}]", model
            return "[Empty response from Gemini]", model

    def get_active_models(self):
        return list(self.client.keys())