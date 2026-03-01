from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


class TeamUpdate(BaseModel):
    team_member_id: Optional[str] = None
    team_member_name: str = ""
    project_id: Optional[str] = None
    project_name: str = ""
    summary: str = ""
    status: str = "in_progress"
    details: str = ""


class ClientUpdate(BaseModel):
    project_id: Optional[str] = None
    project_name: str = ""
    client_name: str = ""
    summary: str = ""
    sentiment: str = "neutral"


class ActionItem(BaseModel):
    description: str = ""
    assigned_to: str = "self"
    due_context: str = ""
    priority: str = "medium"
    is_completed: bool = False


class Blocker(BaseModel):
    description: str = ""
    project_id: Optional[str] = None
    project_name: str = ""
    blocking_who: str = ""
    severity: str = "medium"


class ParsedUpdate(BaseModel):
    team_updates: List[TeamUpdate] = []
    client_updates: List[ClientUpdate] = []
    action_items: List[ActionItem] = []
    blockers: List[Blocker] = []
    general_notes: str = ""


class UpdateCreate(BaseModel):
    raw_text: str
    source: str = "web"


class UpdateResponse(BaseModel):
    id: str = Field(alias="_id")
    raw_text: str
    source: str
    has_screenshot: bool
    screenshot_paths: List[str]
    screenshot_extracted_text: str
    parsed: ParsedUpdate
    ai_confidence: float
    created_at: datetime
    date: str

    class Config:
        populate_by_name = True
