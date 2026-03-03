from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from bson import ObjectId


class ProjectCreate(BaseModel):
    name: str
    code: str
    client_name: str = ""
    description: str = ""
    status: str = "active"


class ProjectUpdate(BaseModel):
    name: Optional[str] = None
    code: Optional[str] = None
    client_name: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None


class ProjectResponse(BaseModel):
    id: str = Field(alias="_id")
    name: str
    code: str
    client_name: str
    client_id: Optional[str] = None
    description: str
    status: str
    team_member_ids: List[str] = []
    auto_created: bool = False
    needs_reference_sync: bool = False
    created_at: datetime
    updated_at: datetime

    class Config:
        populate_by_name = True
        json_encoders = {ObjectId: str}
