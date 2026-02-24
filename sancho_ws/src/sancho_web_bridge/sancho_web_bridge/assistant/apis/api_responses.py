import fastapi.responses as responses

from abc import ABC


class APIResponse(ABC):
    def __init__(self, status_code, content):
        self.status_code = status_code
        self.content = content
    
    def to_fastapi(self):
        return responses.JSONResponse(status_code=self.status_code, content=self.content)

class HTTPException(APIResponse):
    def __init__(self, status_code=400, detail=""):
        super().__init__(status_code, {"detail": detail})

class JSONResponse(APIResponse):
    def __init__(self, status_code=200, content=""):
        super().__init__(status_code, content)