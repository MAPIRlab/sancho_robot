import json

from .prompt_formatter import PromptFormatter


class OpenAIFormatter(PromptFormatter):
    def format(self, prompt_system: str, messages_json: str, user_input: str) -> list:
        messages = []

        if prompt_system:
            messages.append({"role": "system", "content": prompt_system})

        if messages_json:
            messages.extend(json.loads(messages_json))

        if user_input:
            messages.append({"role": "user", "content": user_input})

        return messages