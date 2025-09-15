from abc import ABC, abstractmethod

class AskingAI:

    @abstractmethod
    def get_name(self, message: str):
        pass
    
    @abstractmethod
    def confirm_name(self, message: str):
        pass

    @abstractmethod
    def no_one_known(self, message: str):
        pass

    @abstractmethod
    def some_known(self, known_target: str):
        pass

    @abstractmethod
    def all_known(self, message: str):
        pass