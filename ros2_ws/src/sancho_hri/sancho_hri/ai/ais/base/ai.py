from abc import ABC, abstractmethod

class AI(ABC):

    @abstractmethod
    def on_message(self, message: str, chat_history: list, user_id: str, user_name: str, user_memory: str):
        pass
