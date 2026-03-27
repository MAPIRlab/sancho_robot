import os

from .database.memory_database import MemoryDatabase
from .prompts import MemoryBuilderPrompt
from .log_manager import LogManager
from .engines import LLMEngine


class MemoryManager:

    def __init__(self) -> None:
        self.db_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "database/memory.db"))
        self.db = MemoryDatabase(self.db_path)

        self.llm_engine = LLMEngine()

    def update_memory(self, user_input: str, chat_history: str, faceprint_id: str, faceprint_name: str) -> None:
        current_memory = self.get_memory_text(faceprint_id)
        memory_builder_prompt = MemoryBuilderPrompt(user_input, chat_history, faceprint_id, faceprint_name, current_memory)
        LogManager.info(f"User: {user_input}")
        LogManager.info(f"Memory Builder Prompt system: {memory_builder_prompt.get_prompt_system()}")

        response, _, _, message, success = self.llm_engine.prompt_request(
            prompt_system=memory_builder_prompt.get_prompt_system(),
            user_input=memory_builder_prompt.get_user_prompt(),
            parameters_json=memory_builder_prompt.get_parameters()
        )

        if not success:
            LogManager.error(f"There was a problem with memory builder prompt: {message}")
            return
        
        LogManager.info(f"LLM for Memory Builder Prompt:\n{response}")
        memory_json = MemoryBuilderPrompt.extract_json_from_code_block(response) # Gemini usually puts the response in ```json block
        if not memory_json:
            LogManager.error(f"No JSON format found.")
            return

        memory = MemoryBuilderPrompt.try_json_loads(memory_json)
        if not memory:
            LogManager.error(f"Error on JSON loads.")
            return
        
        new_memory = memory.get("new_memory", None)
        memory_updated = bool(memory.get("memory_updated", False))
        if new_memory is None and memory_updated:
            LogManager.error(f"The JSON response does not contain new memory and says is updated.")
            return
        
        if memory_updated:
            self.db.update_memory(faceprint_id, new_memory)
            LogManager.info(f"Memory of ID {faceprint_id} ({faceprint_name or 'No name'}) has been updated!")

    def direct_update_memory(self, faceprint_id: str, memory_text: str) -> dict:
        return self.db.direct_update_memory(faceprint_id, memory_text)

    def get_all_latest_memories(self) -> list:
        return self.db.get_all_latest_memories()
    
    def get_all_versions(self, faceprint_id: str) -> list:
        return self.db.get_all_versions(faceprint_id)

    def get_memory(self, faceprint_id: str) -> dict:
        return self.db.get_memory(faceprint_id)

    def get_memory_text(self, faceprint_id: str) -> str:
        return self.db.get_memory_text(faceprint_id)