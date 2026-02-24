from typing import Optional, List
from fastapi import APIRouter, HTTPException, Query, Request, Path

from .faceprint_model import Faceprint, FaceprintCreate, FaceprintUpdate, FaceprintDeleteResponse, FaceprintDeleteAllResponse
from .api_utils import APIUtils
from ..apis import FaceprintAPI

from dotenv import load_dotenv

load_dotenv()

router = APIRouter()

endpoint_name = "faceprints"
version = "v1"

faceprint_api: FaceprintAPI = None
def set_faceprint_api(api):
    global faceprint_api
    faceprint_api = api

def get_faceprint_api_dep() -> FaceprintAPI:
    if faceprint_api is None:
        raise HTTPException(status_code=503, detail="Faceprints API no inicializada")
    return faceprint_api

@router.get("", tags=["Faceprints CRUD endpoints"], response_model=List[Faceprint])
async def get_faceprints(
    request: Request,
):
    APIUtils.check_accept_json(request)

    response = get_faceprint_api_dep().get_all_faceprints()
    
    return response.to_fastapi()

@router.get("/{id}", tags=["Faceprints CRUD endpoints"], response_model=Faceprint)
async def get_faceprint_by_id(
    request: Request,
    id: str = Path(description="Id de la persona"),
):
    APIUtils.check_accept_json(request)
    
    response = get_faceprint_api_dep().get_faceprint(id)

    return response.to_fastapi()

@router.post("", tags=["Faceprints CRUD endpoints"], response_model=FaceprintCreate)
async def create_faceprint(
    faceprint_create: FaceprintCreate,
    request: Request
):
    APIUtils.check_accept_json(request)
    APIUtils.check_content_type_json(request)

    update_data = faceprint_create.model_dump(exclude_defaults=True)
    name = update_data["name"]
    image_base64 = update_data["image"]
    
    response = get_faceprint_api_dep().create_faceprint(name, image_base64)
    
    return response.to_fastapi()

@router.put("/{id}", tags=["Faceprints CRUD endpoints"], response_model=Faceprint)
async def update_faceprint(
    id: str,
    faceprint_update: FaceprintUpdate,
    request: Request
):
    APIUtils.check_accept_json(request)
    APIUtils.check_content_type_json(request)

    update_data = faceprint_update.model_dump(exclude_defaults=True)
    response = get_faceprint_api_dep().update_faceprint(id, update_data)

    return response.to_fastapi()
    
@router.delete("/{id}", tags=["Faceprints CRUD endpoints"], response_model=FaceprintDeleteResponse)
async def delete_faceprint(
    id: str,
    request: Request
):
    APIUtils.check_accept_json(request)

    response = get_faceprint_api_dep().delete_faceprint(id)

    return response.to_fastapi()

@router.delete("", tags=["Faceprints CRUD endpoints"], response_model=FaceprintDeleteAllResponse)
async def delete_all_faceprints(
    request: Request
):
    APIUtils.check_accept_json(request)

    response = get_faceprint_api_dep().delete_all_faceprints()

    return response.to_fastapi()