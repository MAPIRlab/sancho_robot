from abc import ABC

from ..intent_classifiers import IntentClassifier
from ..intent_executors import IntentExecutor
from ..response_generators import ResponseGenerator

from ...prompts.commands.commands import COMMANDS


class ModularAI(ABC):
    def __init__(self, classifier: IntentClassifier, executor: IntentExecutor, response_generator: ResponseGenerator):
        self.classifier = classifier
        self.executor = executor
        self.response_generator = response_generator

    def on_message(self, user_input: str, chat_history: list = []) -> str:
        intent, arguments, cl_provider_used, cl_model_used = self.classifier.classify(user_input, chat_history)
        
        if intent != COMMANDS.UNKNOWN:
            details, status, data = self.executor.execute(intent, arguments)

            response, emotion, provider_used, model_used = \
                self.response_generator.generate_response(
                    details, status, intent, arguments, user_input, chat_history
                )
        else:
            data = {}
            response, emotion, provider_used, model_used = \
                self.response_generator.continue_conversation(user_input, chat_history)

        value = {
            "text": response,
            "emotion": emotion,
            "data": data
        }

        return value, intent, arguments, provider_used, model_used