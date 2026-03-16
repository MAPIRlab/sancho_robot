from abc import ABC, abstractmethod


class IntentClassifier(ABC):

    @abstractmethod
    def classify(self, user_input: str, chat_history: list = []):
        pass