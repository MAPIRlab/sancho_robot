from typing import Optional, List
from fastapi import APIRouter, HTTPException, Query, Request, Path

from .llm_model_model import LLMProvider, LLMLoadModel, LLMUnloadModel, LLMActiveModel, LLMResult
from .api_utils import APIUtils
from ..apis import LLMModelAPI

from dotenv import load_dotenv

load_dotenv()

router = APIRouter()

endpoint_name = "llm_models"
version = "v1"

llm_model_api: LLMModelAPI = None
def set_llm_model_api(api):
    global llm_model_api
    llm_model_api = api

def get_llm_model_api_dep() -> LLMModelAPI:
    if llm_model_api is None:
        raise HTTPException(status_code=503, detail="LLM Models API no inicializada")
    return llm_model_api

@router.get("", tags=["LLM Models CRUD endpoints"], response_model=List[LLMProvider])
async def get_llm_providers(
    request: Request,
    providers: Optional[List[str]] = Query(None, description="Lista de proveedores a buscar")
):
    APIUtils.check_accept_json(request)
    
    response = get_llm_model_api_dep().get_all_llm_providers(**({"providers": providers} if providers else {}))
    return response.to_fastapi()

@router.get("/{provider}", tags=["LLM Models CRUD endpoints"], response_model=LLMProvider)
async def get_llm_provider(
    request: Request,
    provider: str = Path(description="Nombre del proveedor")
):
    APIUtils.check_accept_json(request)

    response = get_llm_model_api_dep().get_llm_provider(provider)
    
    return response.to_fastapi()

@router.post("/load", tags=["LLM Models CRUD endpoints"], response_model=LLMResult)
async def load_llm_model(
    llm_load_model: LLMLoadModel,
    request: Request
):
    APIUtils.check_accept_json(request)
    APIUtils.check_content_type_json(request)

    data = llm_load_model.model_dump(exclude_defaults=True)
    provider = data.get("provider")
    model = data.get("model")
    api_key = data.get("api_key", "")

    response = get_llm_model_api_dep().load_llm_model(provider, model, api_key)

    return response.to_fastapi()

@router.post("/unload", tags=["LLM Models CRUD endpoints"], response_model=LLMResult)
async def unload_llm_model(
    llm_unload_model: LLMUnloadModel,
    request: Request
):
    APIUtils.check_accept_json(request)
    APIUtils.check_content_type_json(request)

    data = llm_unload_model.model_dump(exclude_defaults=True)
    provider = data.get("provider")
    model = data.get("model")

    response = get_llm_model_api_dep().unload_llm_model(provider, model)

    return response.to_fastapi()

@router.post("/activate", tags=["LLM Models CRUD endpoints"], response_model=LLMResult)
async def activate_llm_model(
    llm_active_model: LLMActiveModel,
    request: Request
):
    APIUtils.check_accept_json(request)
    APIUtils.check_content_type_json(request)

    data = llm_active_model.model_dump(exclude_defaults=True)
    provider = data.get("provider")
    model = data.get("model")

    response = get_llm_model_api_dep().set_active_llm_model(provider, model)

    return response.to_fastapi()
