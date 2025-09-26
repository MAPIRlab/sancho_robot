import json

from .response_generator import ResponseGenerator

from ...log_manager import LogManager
from ...prompts import UnknownPrompt, SemanticResultPrompt
from ...engines import LLMEngine
from ...prompts.commands import COMMAND_RESUITS


class LLMGenerator(ResponseGenerator):

    EMOTION_MAP = {
        COMMAND_RESUITS.FAILURE: "sad",
        COMMAND_RESUITS.MISSING_ARGUMENT: "neutral",
        COMMAND_RESUITS.SUCCESS: "happy"
    }

    def __init__(self, llm_engine: LLMEngine):
        self.llm_engine = llm_engine
    
    def generate_response(self, details: str, status: str, intent: str, arguments: dict, user_input: str) -> str:
        status_emotion = self.EMOTION_MAP[status]

        semantic_result = SemanticResultPrompt.build_semantic_result(intent, arguments, status, details)
        semantic_result_prompt = SemanticResultPrompt(semantic_result, user_input)
        LogManager.info(f"User: {user_input}")
        LogManager.info(f"Semantic Result Prompt system: {semantic_result_prompt.get_prompt_system()}")

        response, provider_used, model_used, message, success = self.llm_engine.prompt_request(
            prompt_system=semantic_result_prompt.get_prompt_system(),
            user_input=semantic_result_prompt.get_user_prompt(),
            parameters_json=semantic_result_prompt.get_parameters()
        )

        if not success:
            LogManager.error(f"There was a problem with generation prompt: {message}")
            return semantic_result["details"]
   
        LogManager.info(f"LLM for Semantic Result Prompt:\n{response}")
        semantic_result_json = SemanticResultPrompt.extract_json_from_code_block(response) # Gemini usually puts the response in ```json block
        if not semantic_result_json:
            LogManager.error(f"No JSON format found.")

            if "{" not in response and "}" not in response:
                semantic_result_json = json.dumps({ "response": response, "emotion": status_emotion})
                LogManager.info(f"Assuming response is only text.")
            else:
                return details, status_emotion, provider_used, model_used

        semantic_result = SemanticResultPrompt.try_json_loads(semantic_result_json)
        if not semantic_result:
            LogManager.error(f"Error on JSON loads.")
            return details, status_emotion, provider_used, model_used
        
        response = semantic_result.get("response", "")
        emotion = semantic_result.get("emotion", "")
        if not response:
            LogManager.error(f"The JSON response does not contain a text response.")
            return details, status_emotion, provider_used, model_used
        
        if not emotion or emotion not in ["happy", "surprised", "sad", "angry", "bored", "suspicious", "neutral"]:
            LogManager.error(f"❌❌❌❌❌ EMOTION {emotion} INVALID. Default to neutral.")
            emotion = status_emotion

        LogManager.info(f"LLM for Semantic Result Prompt:\n{response}")

        return response, emotion, provider_used, model_used

    def continue_conversation(self, user_input: str, robot_context: dict, chat_history: list, user_id: str, user_name: str, user_memory: str) -> str:
        unknown_prompt = UnknownPrompt(user_input, robot_context, user_id, user_name, user_memory)
        LogManager.info(f"User: {user_input}")
        LogManager.info(f"Unknown Prompt system: {unknown_prompt.get_prompt_system()}")

        response, provider_used, model_used, message, success = self.llm_engine.prompt_request(
            messages_json=json.dumps(chat_history),
            prompt_system=unknown_prompt.get_prompt_system(),
            user_input=unknown_prompt.get_user_prompt(),
            parameters_json=unknown_prompt.get_parameters()
        )

        if not success:
            LogManager.error(f"There was a problem with unknown prompt: {message}")
            return "Lo siento, no te he entendido", "sad", provider_used, model_used
        
        LogManager.info(f"LLM for Unknown Prompt:\n{response}")
        response_json = SemanticResultPrompt.extract_json_from_code_block(response) # Gemini usually puts the response in ```json block
        if not response_json:
            LogManager.error(f"No JSON format found.")

            if "{" not in response and "}" not in response:
                response_json = json.dumps({ "response": response, "emotion": "neutral"})
                LogManager.info(f"Assuming response is only text.")
            else:
                return "Lo siento, no te he entendido", "neutral", provider_used, model_used

        response = SemanticResultPrompt.try_json_loads(response_json)
        if not response:
            LogManager.error(f"Error on JSON loads.")
            return "Lo siento, no te he entendido", "neutral", provider_used, model_used
        
        text_response = response.get("response", "")
        emotion = response.get("emotion", "")
        if not text_response:
            LogManager.error(f"The JSON response does not contain a text response.")
            return "Lo siento, no te he entendido", "neutral", provider_used, model_used
        
        if not emotion or emotion not in ["happy", "surprised", "sad", "angry", "bored", "suspicious", "neutral"]:
            LogManager.error(f"❌❌❌❌❌ EMOTION {emotion} INVALID. Default to neutral.")
            emotion = "neutral"

        LogManager.info(f"LLM for Unknown Prompt:\n{text_response}. Emotion: {emotion}")

        return text_response, emotion, provider_used, model_used
