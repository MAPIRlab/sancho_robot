from abc import ABC, abstractmethod

class AskingAI:

    @abstractmethod
    def get_name(self, message: str):
        pass
    
    @abstractmethod
    def confirm_name(self, message: str):
        pass