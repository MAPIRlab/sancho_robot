from abc import ABC, abstractmethod


class ResponseGenerator(ABC):

    @abstractmethod
    def generate_response(self, details: str, status: str, intent: str, 
                          arguments: dict, user_input: str, chat_history: list) -> str:
        pass

    @abstractmethod
    def continue_conversation(self, user_input: str, chat_history: list) -> str:
        pass