from .base import AI

from ..prompts.commands import COMMANDS


class DummyAI(AI):

    def __init__(self):
        self.provider_used = "Dummy"
        self.model_used = "Dummy"

    def on_message(self, message, chat_history=[]):
        intent = COMMANDS.UNKNOWN
        arguments = {}

        value = {
            "text": message[::-1],
            "emotion": "neutral",
            "data": {}
        }

        return value, intent, arguments, self.provider_used, self.model_used