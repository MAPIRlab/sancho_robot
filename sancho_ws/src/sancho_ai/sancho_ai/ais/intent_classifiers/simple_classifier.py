import re

from .intent_classifier import IntentClassifier

from ...prompts.commands.commands import COMMANDS


class SimpleClassifier(IntentClassifier):
    def __init__(self):
        self.provider_used = "SimpleNLP"
        self.model_used = "RegexRules"

    def classify(self, user_input: str, chat_history=[]):
        user_input = user_input.lower().strip()

        if "foto" in user_input:
            return COMMANDS.TAKE_PICTURE, {}, self.provider_used, self.model_used

        match = re.match(r"^borra a (\w+)", user_input)
        if match:
            return COMMANDS.DELETE_USER, {"user": match.group(1)}, self.provider_used, self.model_used

        match = re.match(r"^renombra a (\w+) como (\w+)", user_input)
        if match:
            return COMMANDS.RENAME_USER, {
                "old_name": match.group(1),
                "new_name": match.group(2)
            }, self.provider_used, self.model_used

        return COMMANDS.UNKNOWN, {}, self.provider_used, self.model_used
