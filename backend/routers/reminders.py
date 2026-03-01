from fastapi import APIRouter, HTTPException
from bson import ObjectId
from datetime import datetime

from backend.database import get_db

router = APIRouter()


@router.get("/reminders")
async def list_reminders(active_only: bool = True):
    """Get reminders, defaulting to active (undismissed) ones."""
    db = get_db()
    query = {"is_dismissed": False} if active_only else {}
    reminders = await db.reminders.find(query).sort("trigger_time", -1).to_list(None)
    for r in reminders:
        r["_id"] = str(r["_id"])
    return reminders


@router.get("/reminders/count")
async def reminder_count():
    """Get count of active reminders (for nav badge)."""
    db = get_db()
    count = await db.reminders.count_documents({"is_dismissed": False})
    return {"count": count}


@router.put("/reminders/{reminder_id}/dismiss")
async def dismiss_reminder(reminder_id: str):
    """Dismiss a reminder."""
    db = get_db()
    result = await db.reminders.update_one(
        {"_id": ObjectId(reminder_id)},
        {"$set": {"is_dismissed": True}},
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Reminder not found")
    return {"status": "dismissed"}


@router.post("/reminders/{reminder_id}/act")
async def act_on_reminder(reminder_id: str):
    """Mark a reminder as acted upon (dismiss + mark sent)."""
    db = get_db()
    result = await db.reminders.update_one(
        {"_id": ObjectId(reminder_id)},
        {"$set": {"is_dismissed": True, "is_sent": True, "sent_via": "web"}},
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Reminder not found")
    return {"status": "acted"}
