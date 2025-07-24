from pydantic import BaseModel, Field
from datetime import datetime

class Log(BaseModel):
    id: int = Field(default=None, example=1)
    timestamp: str = Field(default_factory=str(datetime.now().timestamp()), example="1712345678")
    action: str = Field(example="add_class")
    faceprint_id: str = Field(example="0")
    origin: str = Field(example="ROS")
