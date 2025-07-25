from abc import ABC, abstractmethod

class AI(ABC):

    @abstractmethod
    def on_message(self, message, chat_history=[]):
        pass
