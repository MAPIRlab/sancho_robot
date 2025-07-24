from pydantic import BaseModel, Field
from typing import Optional


class STTModel(BaseModel):
    model: str = Field(example="whisper")
    needs_api_key: bool = Field(example=True)
    loaded: bool = Field(example=True)
    active: bool = Field(example=True)

class STTLoadModel(BaseModel):
    model: str = Field(example="whisper")
    api_key: Optional[str] = Field(default=None, example="...")

class STTUnloadModel(BaseModel):
    model: str = Field(example="whisper")

class STTActiveModel(BaseModel):
    model: str = Field(example="whisper")

class STTResult(BaseModel):
    success: bool = Field(example=True)
    message: str = Field(example="OK")
