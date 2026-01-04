from abc import ABC, abstractmethod


class ResponseGenerator(ABC):

    @abstractmethod
    def generate_response(self, details: str, status: str, intent: str, arguments: dict, user_input: str) -> str:
        pass

    @abstractmethod
    def continue_conversation(self, user_input: str, robot_context: dict, chat_history: list, user_id: str, user_name: str, user_memory: str) -> str:
        pass