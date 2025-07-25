import json
from .prompt_formatter import PromptFormatter


class GeminiFormatter(PromptFormatter):
    def format(self, prompt_system: str, messages_json: str, user_input: str) -> dict:
        messages = []

        if prompt_system:
            messages.append({"role": "user", "parts": [prompt_system.strip()]})
            messages.append({"role": "model", "parts": ["Understood."]})

        if messages_json:
            for msg in json.loads(messages_json):
                if msg["role"] == "user":
                    messages.append({"role": "user", "parts": [msg["content"]]})
                elif msg["role"] == "assistant":
                    messages.append({"role": "model", "parts": [msg["content"]]})

        if user_input:
            messages.append({"role": "user", "parts": [user_input.strip()]})

        return messages