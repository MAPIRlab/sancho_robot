from typing import Optional, List
from fastapi import APIRouter, HTTPException, Query, Request, Path

from .tts_model_model import TTSModel, TTSLoadModel, TTSUnloadModel, TTSActiveModel, TTSResult
from .api_utils import APIUtils
from ..apis import TTSModelAPI

from dotenv import load_dotenv

load_dotenv()

router = APIRouter()

endpoint_name = "tts_models"
version = "v1"

tts_model_api: TTSModelAPI = None
def set_tts_model_api(api):
    global tts_model_api
    tts_model_api = api

@router.get("", tags=["TTS Models CRUD endpoints"], response_model=List[TTSModel])
async def get_tts_models(
    request: Request,
    models: Optional[List[str]] = Query(None, description="Lista de modelos a buscar")
):
    APIUtils.check_accept_json(request)

    try:
        response = tts_model_api.get_all_tts_models(**({ "models": models} if models else {}))
        
        return response.to_fastapi()
    
    except HTTPException as e:
        raise e 
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{model}", tags=["TTS Models CRUD endpoints"], response_model=TTSModel)
async def get_tts_model_by_name(
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
        response = tts_model_api.get_tts_model(model)

        return response.to_fastapi()
    
    except HTTPException as e:
        raise e 
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/load", tags=["TTS Models CRUD endpoints"], response_model=TTSResult)
async def load_tts_model(
    tts_load_model: TTSLoadModel,
    request: Request
):
    APIUtils.check_accept_json(request)
    APIUtils.check_content_type_json(request)

    try:
        data = tts_load_model.model_dump(exclude_defaults=True)
        model = data.get("model")
        api_key = data.get("api_key", "")
        
        response = tts_model_api.load_tts_model(model, api_key)

        return response.to_fastapi()

    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/unload", tags=["TTS Models CRUD endpoints"], response_model=TTSResult)
async def unload_tts_model(
    tts_unload_model: TTSUnloadModel,
    request: Request
):
    APIUtils.check_accept_json(request)
    APIUtils.check_content_type_json(request)

    try:
        data = tts_unload_model.model_dump(exclude_defaults=True)
        model = data.get("model")
        
        response = tts_model_api.unload_tts_model(model)

        return response.to_fastapi()

    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/activate", tags=["TTS Models CRUD endpoints"], response_model=TTSResult)
async def activate_tts_model(
    tts_active_model: TTSActiveModel,
    request: Request
):
    APIUtils.check_accept_json(request)
    APIUtils.check_content_type_json(request)

    try:
        data = tts_active_model.model_dump(exclude_defaults=True)
        model = data.get("model")
        speaker = data.get("speaker")
        
        response = tts_model_api.set_active_tts_model(model, speaker)

        return response.to_fastapi()

    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
