from typing import Optional, List
from fastapi import APIRouter, HTTPException, Query, Request, Path

from .log_model import Log
from .api_utils import APIUtils
from ..apis import LogAPI

from dotenv import load_dotenv

load_dotenv()

router = APIRouter()

endpoint_name = "logs"
version = "v1"

log_api: LogAPI = None
def set_log_api(api):
    global log_api
    log_api = api

def get_log_api_dep() -> LogAPI:
    if log_api is None:
        raise HTTPException(status_code=503, detail="Logs API no inicializada")
    return log_api

@router.get("", tags=["Logs CRUD endpoints"], response_model=List[Log])
async def get_logs(
    request: Request
):
    APIUtils.check_accept_json(request)

    response = get_log_api_dep().get_all_logs()
    
    return response.to_fastapi()

@router.get("/{id}", tags=["Logs CRUD endpoints"], response_model=Log)
async def get_logs_by_id(
    request: Request,
    id: str = Path(description="Id del log")
):
    APIUtils.check_accept_json(request)

    response = get_log_api_dep().get_log_by_id(id)

    return response.to_fastapi()