from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


class DeliveryStatus(BaseModel):
    sent: bool = False
    sent_at: Optional[datetime] = None
    error: Optional[str] = None


class ReportDeliveryStatus(BaseModel):
    email: DeliveryStatus = DeliveryStatus()
    telegram: DeliveryStatus = DeliveryStatus()


class ReportResponse(BaseModel):
    id: str = Field(alias="_id")
    type: str
    date: str
    week_start: Optional[str] = None
    week_end: Optional[str] = None
    content_markdown: str
    content_html: str
    content_plain: str
    delivery_status: ReportDeliveryStatus
    source_update_ids: List[str]
    created_at: datetime

    class Config:
        populate_by_name = True
