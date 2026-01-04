import json

from ..engines import MemoryEngine
from .api_responses import APIResponse, HTTPException, JSONResponse


class MemoryAPI:

    def __init__(self, node):
        self.engine = MemoryEngine(node)

    def get_all_latest_memories(self) -> APIResponse:
        memories_json = self.engine.get_memories_request()
        memories = json.loads(memories_json)
        
        return JSONResponse(content=memories)

    def get_memory(self, faceprint_id: str) -> APIResponse:
        if not faceprint_id:
            return HTTPException(detail="Debes incluir faceprint_id.")

        memory_json = self.engine.get_memories_request(json.dumps({
            "faceprint_id": faceprint_id,
            "versions": False
        }))
        memory = json.loads(memory_json)

        return JSONResponse(content=memory)

    def get_all_versions(self, faceprint_id: str) -> APIResponse:
        if not faceprint_id:
            return HTTPException(detail="Debes incluir faceprint_id.")

        versions_json = self.engine.get_memories_request(json.dumps({
            "faceprint_id": faceprint_id,
            "versions": True
        }))
        versions = json.loads(versions_json)

        return JSONResponse(content=versions)

    def direct_update_memory(self, faceprint_id: str, memory_text: str) -> APIResponse:
        if not faceprint_id:
            return HTTPException(detail="Debes incluir faceprint_id.")
        if memory_text is None:
            return HTTPException(detail="Debes incluir memory_text.")

        updated_json = self.engine.update_memory_request(json.dumps({
            "faceprint_id": faceprint_id,
            "memory_text": memory_text
        }))
        updated = json.loads(updated_json)

        return JSONResponse(content=updated)
