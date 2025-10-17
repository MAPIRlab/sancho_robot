from typing import Optional, List
from fastapi import APIRouter, HTTPException, Query, Request, Path

from .session_model import Session
from .api_utils import APIUtils
from ..apis import SessionAPI

from dotenv import load_dotenv

load_dotenv()

router = APIRouter()

endpoint_name = "sessions"
version = "v1"

session_api: SessionAPI = None # Se podria hacer un archivo de registros, un objeto, en el sancho ai se registra y de aqui se getea y ya.
def set_session_api(api):
    global session_api
    session_api = api

def get_session_api_dep() -> SessionAPI:
    if session_api is None:
        raise HTTPException(status_code=503, detail="Sessions API no inicializada")
    return session_api

@router.get("", tags=["Sessions CRUD endpoints"], response_model=List[Session])
async def get_sessions(
    request: Request,
    faceprint_id: Optional[str] = Query(None, description="ID de un faceprint")
):
    APIUtils.check_accept_json(request)

    response = get_session_api_dep().get_all_sessions(**({ "faceprint_id": faceprint_id} if faceprint_id else {}))
    
    return response.to_fastapi()

@router.get("/summary", tags=["Sessions CRUD endpoints"], response_model=Session)
async def get_sessions_summary(
    request: Request
):
    APIUtils.check_accept_json(request)
    
    response = get_session_api_dep().get_sessions_summary()

    return response.to_fastapi()

@router.get("/{id}", tags=["Sessions CRUD endpoints"], response_model=Session)
async def get_sessions_by_id(
    request: Request,
    id: str = Path(description="Id de la sesión")
):
    APIUtils.check_accept_json(request)

    response = get_session_api_dep().get_session_by_id(id)

    return response.to_fastapi()