from pydantic import BaseModel, Field
from typing import List, Union
from datetime import datetime


class Session(BaseModel):
    id: int = Field(default=None, example=1)
    faceprint_id: str = Field(example="0")
    start_time: str = Field(default_factory=str(datetime.now().timestamp()), example="1712345678")
    end_time: str = Field(default_factory=str(datetime.now().timestamp()), example="1712345678")
    detections: List[List[Union[str, float]]] = Field(
        default_factory=list,
        example=[
            ["1712345678", 0.92, 0.85, ""],
            ["1712345679", 0.88, 0.80, "base64string..."]
        ]
    )
