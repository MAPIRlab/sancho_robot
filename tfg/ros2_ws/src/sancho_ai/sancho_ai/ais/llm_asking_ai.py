import json

from rclpy.node import Node

from .base import AskingAI

from ..engines import LLMEngine
from ..prompts.asking_name_prompt import AskingNamePrompt
from ..prompts.asking_confirm_prompt import AskingConfirmPrompt
from ..log_manager import LogManager


class LLMAskingAI(AskingAI):
    def __init__(self, node: Node = None, provider: str = None, model: str = None):
        self.llm_engine = LLMEngine(node if node else LLMEngine.create_client_node())
        self.provider = provider
        self.model = model

    def get_name(self, message, testing=False):
        prompt = AskingNamePrompt(message)

        response, provider_used, model_used, log_message, success = self.llm_engine.prompt_request(
            prompt_system=prompt.get_prompt_system(),
            user_input=prompt.get_user_prompt(),
            parameters_json=prompt.get_parameters(),
            **{"provider": self.provider, "model": self.model} if (self.provider and self.model) else {}
        )

        meta = {
            "empty_response": not success or not response.strip(),
            "valid_json": False,
            "name_said_present": False,
            "real_response": response
        }

        if not success:
            LogManager.error(f"There was a problem with AskingNamePrompt: {log_message}")
            return ({"name_said": False, "name": ""}, provider_used, model_used, meta) if testing else ({"name_said": False, "name": ""}, provider_used, model_used)

        LogManager.info(f"LLM Response for AskingNamePrompt:\n{response}")
        raw_json = AskingNamePrompt.extract_json_from_code_block(response)
        if not raw_json:
            LogManager.error("No JSON format found.")
            return ({"name_said": False, "name": ""}, provider_used, model_used, meta) if testing else ({"name_said": False, "name": ""}, provider_used, model_used)

        try:
            value = json.loads(raw_json)
            meta["valid_json"] = True
        except Exception as e:
            LogManager.error(f"Error loading JSON: {e}")
            return ({"name_said": False, "name": ""}, provider_used, model_used, meta) if testing else ({"name_said": False, "name": ""}, provider_used, model_used)

        if "name_said" in value and "name" in value:
            meta["name_said_present"] = True
            return (value, provider_used, model_used, meta) if testing else (value, provider_used, model_used)

        LogManager.error("Missing required fields in JSON.")
        return ({"name_said": False, "name": ""}, provider_used, model_used, meta) if testing else ({"name_said": False, "name": ""}, provider_used, model_used)

    def confirm_name(self, message, testing=False):
        prompt = AskingConfirmPrompt(message)

        response, provider_used, model_used, log_message, success = self.llm_engine.prompt_request(
            prompt_system=prompt.get_prompt_system(),
            user_input=prompt.get_user_prompt(),
            parameters_json=prompt.get_parameters(),
            **{"provider": self.provider, "model": self.model} if (self.provider and self.model) else {}
        )

        meta = {
            "empty_response": not success or not response.strip(),
            "valid_json": False,
            "answer_said_present": False,
            "real_response": response
        }

        if not success:
            LogManager.error(f"There was a problem with AskingConfirmPrompt: {log_message}")
            return ({"answer_said": False, "answer": ""}, provider_used, model_used, meta) if testing else ({"answer_said": False, "answer": ""}, provider_used, model_used)

        LogManager.info(f"LLM Response for AskingConfirmPrompt:\n{response}")
        raw_json = AskingConfirmPrompt.extract_json_from_code_block(response)
        if not raw_json:
            LogManager.error("No JSON format found.")
            return ({"answer_said": False, "answer": ""}, provider_used, model_used, meta) if testing else ({"answer_said": False, "answer": ""}, provider_used, model_used)

        try:
            value = json.loads(raw_json)
            meta["valid_json"] = True
        except Exception as e:
            LogManager.error(f"Error loading JSON: {e}")
            return ({"answer_said": False, "answer": ""}, provider_used, model_used, meta) if testing else ({"answer_said": False, "answer": ""}, provider_used, model_used)

        if "answer_said" in value and "answer" in value:
            meta["answer_said_present"] = True
            return (value, provider_used, model_used, meta) if testing else (value, provider_used, model_used)

        LogManager.error("Missing required fields in JSON.")
        return ({"answer_said": False, "answer": ""}, provider_used, model_used, meta) if testing else ({"answer_said": False, "answer": ""}, provider_used, model_used)
