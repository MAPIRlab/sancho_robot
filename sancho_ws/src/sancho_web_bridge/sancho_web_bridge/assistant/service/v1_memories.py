from typing import List
from fastapi import APIRouter, HTTPException, Request, Path

from .memory_model import Memory, MemoryText
from .api_utils import APIUtils
from ..apis import MemoryAPI

from dotenv import load_dotenv
load_dotenv()

router = APIRouter()

endpoint_name = "memories"
version = "v1"

memory_api: MemoryAPI = None
def set_memory_api(api):
    global memory_api
    memory_api = api

def get_memory_api_dep() -> MemoryAPI:
    if memory_api is None:
        raise HTTPException(status_code=503, detail="Memories API no inicializada")
    return memory_api

@router.get("", tags=["Memories endpoints"], response_model=List[Memory])
async def get_all_latest_memories(
    request: Request,
):
    APIUtils.check_accept_json(request)

    response = get_memory_api_dep().get_all_latest_memories()

    return response.to_fastapi()

@router.get("/{faceprint_id}", tags=["Memories endpoints"], response_model=Memory)
async def get_memory_by_faceprint(
    request: Request,
    faceprint_id: str = Path(description="Id del faceprint"),
):
    APIUtils.check_accept_json(request)

    response = get_memory_api_dep().get_memory(faceprint_id)

    return response.to_fastapi()

@router.get("/{faceprint_id}/versions", tags=["Memories endpoints"], response_model=List[Memory])
async def get_memory_versions(
    request: Request,
    faceprint_id: str = Path(description="Id del faceprint"),
):
    APIUtils.check_accept_json(request)

    response = get_memory_api_dep().get_all_versions(faceprint_id)

    return response.to_fastapi()

@router.put("/{faceprint_id}", tags=["Memories endpoints"], response_model=Memory)
async def put_update_memory(
    faceprint_id: str,
    memory_update: MemoryText,
    request: Request
):
    APIUtils.check_accept_json(request)
    APIUtils.check_content_type_json(request)

    update_data = memory_update.model_dump(exclude_defaults=True)
    response = get_memory_api_dep().direct_update_memory(faceprint_id, update_data["memory_text"])

    return response.to_fastapi()
