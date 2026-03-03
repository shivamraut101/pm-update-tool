from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


class ClientCreate(BaseModel):
    name: str
    project_ids: List[str] = []
    contact_email: str = ""


class ClientResponse(BaseModel):
    id: str = Field(alias="_id")
    name: str
    project_ids: List[str] = []
    contact_email: str = ""
    auto_created: bool = False
    created_at: datetime

    class Config:
        populate_by_name = True
