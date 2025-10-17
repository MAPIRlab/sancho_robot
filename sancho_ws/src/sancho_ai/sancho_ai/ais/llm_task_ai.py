import json
from rclpy.node import Node
from typing import Any

from .base import TaskAI
from ..engines import LLMEngine
from ..prompts import Prompt, ExtractNamePrompt, ConfirmNamePrompt, NoOneKnownPrompt, SomeKnownPrompt, AllKnownPrompt
from ..log_manager import LogManager


class LLMTaskAI(TaskAI): # Only callable tasks as a single SanchoPrompt, no tasks like classification or memory builder

    _llm_engine: LLMEngine | None = None
    _provider: str | None = None
    _model: str | None = None

    @classmethod
    def init(cls, node: Node | None = None, provider: str | None = None, model: str | None = None):
        cls._llm_engine = LLMEngine(node)
        cls._provider = provider
        cls._model = model

    @classmethod
    def get_name(cls, message: str, _: dict) -> tuple[dict[str, Any], str, str]:
        return cls._execute(ExtractNamePrompt(message), required=["name_said", "name"], default={"name_said": False, "name": ""})

    @classmethod
    def confirm_name(cls, message: str, _: dict) -> tuple[dict[str, Any], str, str]:
        return cls._execute(ConfirmNamePrompt(message), required=["answer_said", "answer"], default={"answer_said": False, "answer": ""})

    @classmethod
    def no_one_known(cls, message: str, _: dict) -> tuple[dict[str, Any], str, str]:
        return cls._execute(NoOneKnownPrompt(message), required=["response"], default={"response": ""})

    @classmethod
    def some_known(cls, message: str, args: dict) -> tuple[dict[str, Any], str, str]:
        return cls._execute(SomeKnownPrompt(message, args.get("people", "")), required=["response"], default={"response": ""})

    @classmethod
    def all_known(cls, message: str, args: dict) -> tuple[dict[str, Any], str, str]:
        return cls._execute(AllKnownPrompt(message, args.get("people", "")), required=["response"], default={"response": ""})

    @classmethod
    def _execute(cls, prompt_obj: Prompt, required: list[str], default: dict[str, Any]) -> tuple[dict[str, Any], str, str]:
        prompt_name = prompt_obj.__class__.__name__
        response, provider_used, model_used, log_message, success = cls._engine().prompt_request(
            prompt_system=prompt_obj.get_prompt_system(),
            user_input=prompt_obj.get_user_prompt(),
            parameters_json=prompt_obj.get_parameters(),
            **{"provider": cls._provider, "model": cls._model} if (cls._provider and cls._model) else {}
        )

        if not success:
            LogManager.error(f"There was a problem with {prompt_name}: {log_message}")
            return default, provider_used, model_used
        
        LogManager.info(f"LLM Response for {prompt_name}:\n{response}")
        raw_json = Prompt.extract_json_from_code_block(response)
        if not raw_json:
            LogManager.error(f"No JSON format found for {prompt_name}.")
            return default, provider_used, model_used
        
        try:
            value = json.loads(raw_json)
        except Exception as e:
            LogManager.error(f"Error loading JSON for {prompt_name}: {e}")
            return default, provider_used, model_used
        
        if all(k in value for k in required):
            return value, provider_used, model_used
        
        LogManager.error(f"Missing required fields in JSON for {prompt_name}: expected {required}, got {list(value.keys())}")
        return default, provider_used, model_used

    @classmethod
    def _engine(cls) -> LLMEngine:
        if cls._llm_engine is None:
            cls._llm_engine = LLMEngine()
        return cls._llm_engine