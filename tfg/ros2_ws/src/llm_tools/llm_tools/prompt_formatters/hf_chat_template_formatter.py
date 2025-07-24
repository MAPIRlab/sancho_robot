import json
from transformers import PreTrainedTokenizerBase
from .prompt_formatter import PromptFormatter


class HFChatTemplateFormatter(PromptFormatter):
    def __init__(self, tokenizer: PreTrainedTokenizerBase):
        self.tokenizer = tokenizer

    def format(self, prompt_system: str, messages_json: str, user_input: str) -> str:
        messages = []

        if prompt_system:
            messages.append({"role": "system", "content": prompt_system})

        if messages_json:
            messages.extend(json.loads(messages_json))

        if user_input:
            messages.append({"role": "user", "content": user_input})
            
        return self.tokenizer.apply_chat_template(messages, add_generation_prompt=True, return_tensors="pt")
