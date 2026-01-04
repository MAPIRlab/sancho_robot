from abc import ABC, abstractmethod


class BaseProvider(ABC):

    @abstractmethod
    def embedding(self, user_input, model):
        pass

    @abstractmethod
    def prompt(self, user_input, model, prompt_system, messages_json, parameters_json): 
        pass

    @abstractmethod
    def load(self, models):
        pass

    @abstractmethod
    def unload(self, models):
        pass

    @abstractmethod
    def get_active_models(self):
        pass