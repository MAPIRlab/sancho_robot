from abc import ABC, abstractmethod

class PromptFormatter(ABC):
    @abstractmethod
    def format(self, prompt_system: str, messages_json: str, user_input: str) -> str | dict:
        pass