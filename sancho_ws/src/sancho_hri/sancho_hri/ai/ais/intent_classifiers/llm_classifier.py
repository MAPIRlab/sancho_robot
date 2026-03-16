from .intent_classifier import IntentClassifier

from ...log_manager import LogManager
from ...engines import LLMEngine
from ...prompts.classification_prompt import ClassificationPrompt
from ...prompts.commands.commands import COMMANDS


class LLMClassifier(IntentClassifier):

    def __init__(self, llm_engine: LLMEngine, provider: str = None, model: str = None):
        self.llm_engine = llm_engine
        self.provider = provider
        self.model = model

    def classify(self, user_input, chat_history=[], testing=False):
        classification_prompt = ClassificationPrompt(user_input, chat_history)

        LogManager.info(f"User: {user_input}")
        response, provider_used, model_used, message, success = self.llm_engine.prompt_request(
            prompt_system=classification_prompt.get_prompt_system(),
            user_input=classification_prompt.get_user_prompt(),
            parameters_json=classification_prompt.get_parameters(),
            **{"provider": self.provider, "model": self.model} if (self.provider and self.model) else {}
        )

        meta = {
            "empty_response": not success or not response.strip(),
            "valid_json": False,
            "intent_present": False,
            "real_response": response
        }

        if not success:
            LogManager.error(f"There was a problem with classification prompt: {message}")
            result = (COMMANDS.UNKNOWN, {}, provider_used, model_used)
            return (*result, meta) if testing else result

        LogManager.info(f"LLM for Classification Prompt:\n{response}")
        classification_response_json = ClassificationPrompt.extract_json_from_code_block(response)

        if not classification_response_json:
            LogManager.error(f"No JSON format found.")
            result = (COMMANDS.UNKNOWN, {}, provider_used, model_used)
            return (*result, meta) if testing else result

        classification_response = ClassificationPrompt.try_json_loads(classification_response_json)
        if not classification_response:
            LogManager.error(f"Error on JSON loads.")
            result = (COMMANDS.UNKNOWN, {}, provider_used, model_used)
            return (*result, meta) if testing else result

        meta["valid_json"] = True

        intent = classification_response.get("intent", "")
        arguments = classification_response.get("arguments", {})
        if not intent:
            LogManager.error(f"The JSON response does not contain an intent.")
            result = (COMMANDS.UNKNOWN, {}, provider_used, model_used)
            return (*result, meta) if testing else result

        meta["intent_present"] = True

        if intent not in list(COMMANDS):
            LogManager.error(f"❌❌❌❌❌ PROMPT CLASSIFIED AS INVALID INTENT: {intent}")
            intent = COMMANDS.UNKNOWN
            arguments = {}

        result = (intent, arguments, provider_used, model_used)
        return (*result, meta) if testing else result
