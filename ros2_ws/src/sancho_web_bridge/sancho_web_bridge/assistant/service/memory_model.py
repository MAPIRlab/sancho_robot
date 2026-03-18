from pydantic import BaseModel, Field
from datetime import datetime
from typing import List


class Memory(BaseModel):
    faceprint_id: str = Field(example="0")
    version: int = Field(example=3)
    memory_text: str = Field(example="Vive en Málaga\nLe gusta el café")
    created_at: str = Field(default=str(datetime.now().timestamp()), example="1712345678")


class MemoryText(BaseModel):
    memory_text: str = Field(example="Vive en Málaga\nLe gusta el café\nEs experto en fútbol")
