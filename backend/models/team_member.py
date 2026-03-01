from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from bson import ObjectId


class TeamMemberCreate(BaseModel):
    name: str
    nickname: str = ""
    aliases: List[str] = []
    role: str = ""
    email: str = ""
    project_ids: List[str] = []


class TeamMemberUpdate(BaseModel):
    name: Optional[str] = None
    nickname: Optional[str] = None
    aliases: Optional[List[str]] = None
    role: Optional[str] = None
    email: Optional[str] = None
    project_ids: Optional[List[str]] = None
    is_active: Optional[bool] = None


class TeamMemberResponse(BaseModel):
    id: str = Field(alias="_id")
    name: str
    nickname: str
    aliases: List[str]
    role: str
    email: str
    project_ids: List[str]
    is_active: bool
    created_at: datetime

    class Config:
        populate_by_name = True
        json_encoders = {ObjectId: str}
