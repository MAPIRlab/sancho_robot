from typing import Optional, List
from fastapi import APIRouter, HTTPException, Query, Request, Path

from .stt_model_model import STTModel, STTLoadModel, STTUnloadModel, STTActiveModel, STTResult
from .api_utils import APIUtils
from ..apis import STTModelAPI

from dotenv import load_dotenv

load_dotenv()

router = APIRouter()

endpoint_name = "stt_models"
version = "v1"

stt_model_api: STTModelAPI = None
def set_stt_model_api(api):
    global stt_model_api
    stt_model_api = api

@router.get("", tags=["STT Models CRUD endpoints"], response_model=List[STTModel])
async def get_stt_models(
    request: Request,
    models: Optional[List[str]] = Query(None, description="Lista de modelos a buscar")
):
    APIUtils.check_accept_json(request)

    try:
        response = stt_model_api.get_all_stt_models(**({ "models": models } if models else {}))

        return response.to_fastapi()

    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{model}", tags=["STT Models CRUD endpoints"], response_model=STTModel)
async def get_stt_model_by_name(
    request: Request,
    model: str = Path(description="Nombre del modelo"),
    fields: Optional[str] = Query(None, description="Campos específicos a devolver"),
    sort: Optional[str] = Query(None, description="Campos por los que ordenar, separados por comas"),
    offset: int = Query(default=0, description="Índice de inicio para los resultados de la paginación"),
    limit: int = Query(default=10, description="Cantidad de marcadores a devolver, por defecto 10"),
    hateoas: Optional[bool] = Query(default=False, description="Incluir enlace HATEOAS")
):
    APIUtils.check_accept_json(request)

    try:
        response = stt_model_api.get_stt_model(model)

        return response.to_fastapi()

    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/load", tags=["STT Models CRUD endpoints"], response_model=STTResult)
async def load_stt_model(
    stt_load_model: STTLoadModel,
    request: Request
):
    APIUtils.check_accept_json(request)
    APIUtils.check_content_type_json(request)

    try:
        data = stt_load_model.model_dump(exclude_defaults=True)
        model = data.get("model")
        api_key = data.get("api_key", "")

        response = stt_model_api.load_stt_model(model, api_key)

        return response.to_fastapi()

    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/unload", tags=["STT Models CRUD endpoints"], response_model=STTResult)
async def unload_stt_model(
    stt_unload_model: STTUnloadModel,
    request: Request
):
    APIUtils.check_accept_json(request)
    APIUtils.check_content_type_json(request)

    try:
        data = stt_unload_model.model_dump(exclude_defaults=True)
        model = data.get("model")

        response = stt_model_api.unload_stt_model(model)

        return response.to_fastapi()

    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/activate", tags=["STT Models CRUD endpoints"], response_model=STTResult)
async def activate_stt_model(
    stt_active_model: STTActiveModel,
    request: Request
):
    APIUtils.check_accept_json(request)
    APIUtils.check_content_type_json(request)

    try:
        data = stt_active_model.model_dump(exclude_defaults=True)
        model = data.get("model")

        response = stt_model_api.set_active_stt_model(model)

        return response.to_fastapi()

    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
