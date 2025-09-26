from .database.memory_database import MemoryDatabase


class MemoryManager:

    def __init__(self):
        self.db = MemoryDatabase()

    def update_memory(self, faceprint_id: str, chat_history: list): # Chat history includes last user prompt and assistant answer
        pass

    def get_memory(self, faceprint_id: str):
        return self.db.get_memory(faceprint_id)