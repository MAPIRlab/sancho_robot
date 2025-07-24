from typing import Optional, List
from fastapi import APIRouter, HTTPException, Query, Request, Path

from .faceprint_model import Faceprint, FaceprintCreate, FaceprintUpdate, FaceprintDeleteResponse
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

@router.get("", tags=["Faceprints CRUD endpoints"], response_model=List[Faceprint])
async def get_faceprints(
    request: Request,
):
    APIUtils.check_accept_json(request)

    try:
        response = faceprint_api.get_all_faceprints()
        
        return response.to_fastapi()
    
    except HTTPException as e:
        raise e 
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{id}", tags=["Faceprints CRUD endpoints"], response_model=Faceprint)
async def get_faceprint_by_id(
    request: Request,
    id: str = Path(description="Id de la persona"),
):
    APIUtils.check_accept_json(request)
    
    try:
        response = faceprint_api.get_faceprint(id)

        return response.to_fastapi()
    
    except HTTPException as e:
        raise e 
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("", tags=["Faceprints CRUD endpoints"], response_model=FaceprintCreate)
async def create_faceprint(
    faceprint_create: FaceprintCreate,
    request: Request
):
    APIUtils.check_accept_json(request)
    APIUtils.check_content_type_json(request)

    try:
        update_data = faceprint_create.model_dump(exclude_defaults=True)
        name = update_data["name"]
        image_base64 = update_data["image"]
        
        response = faceprint_api.create_faceprint(name, image_base64)

        return response.to_fastapi()

    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/{id}", tags=["Faceprints CRUD endpoints"], response_model=Faceprint)
async def update_faceprint(
    id: str,
    faceprint_update: FaceprintUpdate,
    request: Request
):
    APIUtils.check_accept_json(request)
    APIUtils.check_content_type_json(request)

    try:
        update_data = faceprint_update.model_dump(exclude_defaults=True)
        response = faceprint_api.update_faceprint(id, update_data)

        return response.to_fastapi()
    
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
@router.delete("/{id}", tags=["Faceprints CRUD endpoints"], response_model=FaceprintDeleteResponse)
async def delete_faceprint(
    id: str,
    request: Request
):
    APIUtils.check_accept_json(request)

    try:
        response = faceprint_api.delete_faceprint(id)

        return response.to_fastapi()
    
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
