from .database.memory_database import MemoryDatabase


class MemoryManager:

    def __init__(self):
        self.db = MemoryDatabase()

    def update_memory(self, user_id, chat_history): # Chat history includes last user prompt and assistant answer
        pass