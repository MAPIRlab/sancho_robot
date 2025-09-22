import json
from typing import Any

from rclpy.node import Node

from .base import TaskAI
from ..engines import LLMEngine
from ..prompts import Prompt, ExtractNamePrompt, ConfirmNamePrompt, NoOneKnownPrompt, SomeKnownPrompt, AllKnownPrompt
from ..log_manager import LogManager


class LLMTaskAI(TaskAI):
    def __init__(self, node: Node | None = None, provider: str | None = None, model: str | None = None):
        self.llm_engine = LLMEngine(node if node else LLMEngine.create_client_node())
        self.provider = provider
        self.model = model

    def get_name(self, message: str) -> tuple[dict[str, Any], str, str]:
        return self._execute(ExtractNamePrompt(message), required=["name_said", "name"], default={"name_said": False, "name": ""})

    def confirm_name(self, message: str) -> tuple[dict[str, Any], str, str]:
        return self._execute(ConfirmNamePrompt(message), required=["answer_said", "answer"], default={"answer_said": False, "answer": ""})

    def no_one_known(self, message: str) -> tuple[dict[str, Any], str, str]:
        return self._execute(NoOneKnownPrompt(message), required=["response"], default={"response": ""})

    def some_known(self, message: str) -> tuple[dict[str, Any], str, str]:
        return self._execute(SomeKnownPrompt(message), required=["response"], default={"response": ""})

    def all_known(self, message: str) -> tuple[dict[str, Any], str, str]:
        return self._execute(AllKnownPrompt(message), required=["response"], default={"response": ""})

    def _execute(self, prompt_obj: Prompt, required_keys: list[str], default_payload: dict[str, Any]) -> tuple[dict[str, Any], str, str]:
        prompt_name = prompt_obj.__class__.__name__
        response, provider_used, model_used, log_message, success = self.llm_engine.prompt_request(
            prompt_system=prompt_obj.get_prompt_system(),
            user_input=prompt_obj.get_user_prompt(),
            parameters_json=prompt_obj.get_parameters(),
            **{"provider": self.provider, "model": self.model} if (self.provider and self.model) else {}
        )

        if not success:
            LogManager.error(f"There was a problem with {prompt_name}: {log_message}")
            return default_payload, provider_used, model_used
        
        LogManager.info(f"LLM Response for {prompt_name}:\n{response}")
        raw_json = Prompt.extract_json_from_code_block(prompt_obj, response)
        if not raw_json:
            LogManager.error(f"No JSON format found for {prompt_name}.")
            return default_payload, provider_used, model_used
        
        try:
            value = json.loads(raw_json)
        except Exception as e:
            LogManager.error(f"Error loading JSON for {prompt_name}: {e}")
            return default_payload, provider_used, model_used
        
        if all(k in value for k in required_keys):
            return value, provider_used, model_used
        
        LogManager.error(f"Missing required fields in JSON for {prompt_name}: expected {required_keys}, got {list(value.keys())}")
        return default_payload, provider_used, model_used
