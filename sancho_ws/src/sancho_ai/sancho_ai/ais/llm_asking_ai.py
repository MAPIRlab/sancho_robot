import json

from rclpy.node import Node

from .base import AskingAI

from ..engines import LLMEngine
from ..prompts import Prompt, AskingNamePrompt, AskingConfirmPrompt, NoOneKnownPrompt, SomeKnownPrompt, AllKnownPrompt
from ..log_manager import LogManager


class LLMAskingAI(AskingAI): # Refactorizar esto para no repetir tanto codigo y renombrar eso de "AskingAI"
    def __init__(self, node: Node = None, provider: str = None, model: str = None):
        self.llm_engine = LLMEngine(node if node else LLMEngine.create_client_node())
        self.provider = provider
        self.model = model

    def get_name(self, message):
        prompt = AskingNamePrompt(message)

        response, provider_used, model_used, log_message, success = self.llm_engine.prompt_request(
            prompt_system=prompt.get_prompt_system(),
            user_input=prompt.get_user_prompt(),
            parameters_json=prompt.get_parameters(),
            **{"provider": self.provider, "model": self.model} if (self.provider and self.model) else {}
        )

        if not success:
            LogManager.error(f"There was a problem with AskingNamePrompt: {log_message}")
            return {"name_said": False, "name": ""}, provider_used, model_used

        LogManager.info(f"LLM Response for AskingNamePrompt:\n{response}")
        raw_json = Prompt.extract_json_from_code_block(response)
        if not raw_json:
            LogManager.error("No JSON format found.")
            return {"name_said": False, "name": ""}, provider_used, model_used

        try:
            value = json.loads(raw_json)
        except Exception as e:
            LogManager.error(f"Error loading JSON: {e}")
            return {"name_said": False, "name": ""}, provider_used, model_used

        if "name_said" in value and "name" in value:
            return value, provider_used, model_used

        LogManager.error("Missing required fields in JSON.")
        return {"name_said": False, "name": ""}, provider_used, model_used

    def confirm_name(self, message):
        prompt = AskingConfirmPrompt(message)

        response, provider_used, model_used, log_message, success = self.llm_engine.prompt_request(
            prompt_system=prompt.get_prompt_system(),
            user_input=prompt.get_user_prompt(),
            parameters_json=prompt.get_parameters(),
            **{"provider": self.provider, "model": self.model} if (self.provider and self.model) else {}
        )

        if not success:
            LogManager.error(f"There was a problem with AskingConfirmPrompt: {log_message}")
            return {"answer_said": False, "answer": ""}, provider_used, model_used

        LogManager.info(f"LLM Response for AskingConfirmPrompt:\n{response}")
        raw_json = AskingConfirmPrompt.extract_json_from_code_block(response)
        if not raw_json:
            LogManager.error("No JSON format found.")
            return {"answer_said": False, "answer": ""}, provider_used, model_used

        try:
            value = json.loads(raw_json)
        except Exception as e:
            LogManager.error(f"Error loading JSON: {e}")
            return {"answer_said": False, "answer": ""}, provider_used, model_used

        if "answer_said" in value and "answer" in value:
            return value, provider_used, model_used

        LogManager.error("Missing required fields in JSON.")
        return {"answer_said": False, "answer": ""}, provider_used, model_used
    
    def no_one_known(self, message):
        prompt = NoOneKnownPrompt(message)

        response, provider_used, model_used, log_message, success = self.llm_engine.prompt_request(
            prompt_system=prompt.get_prompt_system(),
            user_input=prompt.get_user_prompt(),
            parameters_json=prompt.get_parameters(),
            **{"provider": self.provider, "model": self.model} if (self.provider and self.model) else {}
        )

        if not success:
            LogManager.error(f"There was a problem with NoOneKnownPrompt: {log_message}")
            return {"response": ""}, provider_used, model_used

        LogManager.info(f"LLM Response for NoOneKnownPrompt:\n{response}")
        raw_json = NoOneKnownPrompt.extract_json_from_code_block(response)
        if not raw_json:
            LogManager.error("No JSON format found.")
            return {"response": ""}, provider_used, model_used

        try:
            value = json.loads(raw_json)
        except Exception as e:
            LogManager.error(f"Error loading JSON: {e}")
            return {"response": ""}, provider_used, model_used

        if "response" in value:
            return value, provider_used, model_used

        LogManager.error("Missing required fields in JSON.")
        return {"response": ""}, provider_used, model_used
    
    def some_known(self, message):
        prompt = SomeKnownPrompt(message)

        response, provider_used, model_used, log_message, success = self.llm_engine.prompt_request(
            prompt_system=prompt.get_prompt_system(),
            user_input=prompt.get_user_prompt(),
            parameters_json=prompt.get_parameters(),
            **{"provider": self.provider, "model": self.model} if (self.provider and self.model) else {}
        )

        if not success:
            LogManager.error(f"There was a problem with SomeKnownPrompt: {log_message}")
            return {"response": ""}, provider_used, model_used

        LogManager.info(f"LLM Response for SomeKnownPrompt:\n{response}")
        raw_json = SomeKnownPrompt.extract_json_from_code_block(response)
        if not raw_json:
            LogManager.error("No JSON format found.")
            return {"response": ""}, provider_used, model_used

        try:
            value = json.loads(raw_json)
        except Exception as e:
            LogManager.error(f"Error loading JSON: {e}")
            return {"response": ""}, provider_used, model_used

        if "response" in value:
            return value, provider_used, model_used

        LogManager.error("Missing required fields in JSON.")
        return {"response": ""}, provider_used, model_used
    
    def all_known(self, message):
        prompt = AllKnownPrompt(message)

        response, provider_used, model_used, log_message, success = self.llm_engine.prompt_request(
            prompt_system=prompt.get_prompt_system(),
            user_input=prompt.get_user_prompt(),
            parameters_json=prompt.get_parameters(),
            **{"provider": self.provider, "model": self.model} if (self.provider and self.model) else {}
        )

        if not success:
            LogManager.error(f"There was a problem with AllKnownPrompt: {log_message}")
            return {"response": ""}, provider_used, model_used

        LogManager.info(f"LLM Response for AllKnownPrompt:\n{response}")
        raw_json = AllKnownPrompt.extract_json_from_code_block(response)
        if not raw_json:
            LogManager.error("No JSON format found.")
            return {"response": ""}, provider_used, model_used

        try:
            value = json.loads(raw_json)
        except Exception as e:
            LogManager.error(f"Error loading JSON: {e}")
            return {"response": ""}, provider_used, model_used

        if "response" in value:
            return value, provider_used, model_used

        LogManager.error("Missing required fields in JSON.")
        return {"response": ""}, provider_used, model_used