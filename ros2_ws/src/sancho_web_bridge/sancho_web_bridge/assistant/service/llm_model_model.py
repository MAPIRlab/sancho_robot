from pydantic import BaseModel, Field
from typing import Optional, List


class LLMModel(BaseModel):
    model: str = Field(example="gpt-3.5-turbo")
    loaded: bool = Field(example=True)
    active: bool = Field(example=False)

class LLMProvider(BaseModel):
    provider: str = Field(example="openai")
    needs_api_key: bool = Field(example=True)
    executed_locally: bool = Field(example=False)
    models: List[LLMModel] = Field(example=[
        {"model": "gpt-3.5-turbo", "loaded": True, "active": False},
        {"model": "gpt-4", "loaded": False, "active": False}
    ])

class LLMLoadModel(BaseModel):
    provider: str = Field(example="openai")
    model: str = Field(example="gpt-3.5-turbo")
    api_key: Optional[str] = Field(default=None, example="sk-...")

class LLMUnloadModel(BaseModel):
    provider: str = Field(example="openai")
    model: str = Field(example="gpt-3.5-turbo")

class LLMActiveModel(BaseModel):
    provider: str = Field(example="openai")
    model: str = Field(example="gpt-3.5-turbo")

class LLMResult(BaseModel):
    success: bool = Field(example=True)
    message: str = Field(example="Modelo activado correctamente")
