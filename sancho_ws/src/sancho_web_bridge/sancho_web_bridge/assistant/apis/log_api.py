import json

from ..engines import LogEngine
from .api_responses import JSONResponse, APIResponse


class LogAPI:

    def __init__(self, node):
        self.engine = LogEngine(node)

    def get_all_logs(self) -> APIResponse:
        logs_json = self.engine.get_logs_request()
        
        logs = json.loads(logs_json)

        return JSONResponse(content=logs)

    def get_log_by_id(self, id: str) -> APIResponse:
        log_json = self.engine.get_logs_request(json.dumps({ "id": id }))
        log = json.loads(log_json)

        return JSONResponse(content=log)
