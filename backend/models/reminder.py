from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class ReminderCreate(BaseModel):
    type: str
    message: str
    priority: str = "medium"
    related_project_id: Optional[str] = None
    related_action_item: Optional[str] = None
    trigger_time: datetime


class ReminderResponse(BaseModel):
    id: str = Field(alias="_id")
    type: str
    message: str
    priority: str
    related_project_id: Optional[str]
    related_action_item: Optional[str]
    trigger_time: datetime
    is_dismissed: bool
    is_sent: bool
    sent_via: Optional[str]
    last_alerted_at: Optional[datetime] = None
    dismissed_at: Optional[datetime] = None
    dismissed_reason: Optional[str] = None
    created_at: datetime

    class Config:
        populate_by_name = True
