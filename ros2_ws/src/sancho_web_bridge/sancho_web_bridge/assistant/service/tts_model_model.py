from pydantic import BaseModel, Field
from typing import List, Optional


class TTSModel(BaseModel):
    model: str = Field(example="piper")
    speakers: List[str] = Field(default_factory=list, example=["davefx", "sharvard"])
    needs_api_key: bool = Field(example=True)
    loaded: bool = Field(example=True)
    active: bool = Field(example=True)
    speaker: Optional[str] = Field(default=None, description="Voz activa si el modelo está activo", example="davefx")

class TTSLoadModel(BaseModel):
    model: str = Field(example="piper")
    api_key: Optional[str] = Field(default=None, example="...")

class TTSUnloadModel(BaseModel):
    model: str = Field(example="piper")

class TTSActiveModel(BaseModel):
    model: str = Field(example="piper")
    speaker: str = Field(example="davefx")

class TTSResult(BaseModel):
    success: bool = Field(example=True)
    message: str = Field(example="OK")