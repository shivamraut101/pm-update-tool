from fastapi import APIRouter

from backend.database import get_db
from backend.config import settings
from backend.utils.date_helpers import today_str

router = APIRouter()


@router.get("/dashboard")
async def dashboard_data():
    """Aggregated dashboard stats and data."""
    db = get_db()
    date = today_str()

    # Today's stats
    today_updates = await db.updates.count_documents({"date": date})
    active_projects = await db.projects.count_documents({"status": "active"})
    active_members = await db.team_members.count_documents({"is_active": True})
    active_reminders = await db.reminders.count_documents({"is_dismissed": False})

    # Recent updates
    recent_updates = await db.updates.find({"date": date}).sort("created_at", -1).to_list(10)
    for u in recent_updates:
        u["_id"] = str(u["_id"])

    # Active blockers from today
    blockers = []
    for u in recent_updates:
        for b in u.get("parsed", {}).get("blockers", []):
            blockers.append(b)

    # Pending action items
    action_items = []
    for u in recent_updates:
        for a in u.get("parsed", {}).get("action_items", []):
            if not a.get("is_completed", False):
                action_items.append(a)

    # Last report
    last_report = await db.reports.find_one(sort=[("created_at", -1)])
    if last_report:
        last_report["_id"] = str(last_report["_id"])

    return {
        "today_updates": today_updates,
        "active_projects": active_projects,
        "active_members": active_members,
        "active_reminders": active_reminders,
        "recent_updates": recent_updates,
        "blockers": blockers,
        "action_items": action_items,
        "last_report": last_report,
        "date": date,
    }


@router.get("/dashboard/chat")
async def chat_data():
    """Today's updates for the chat view."""
    db = get_db()
    date = today_str()
    today_updates = await db.updates.find({"date": date}).sort("created_at", -1).to_list(50)
    for u in today_updates:
        u["_id"] = str(u["_id"])
    return {"updates": today_updates, "date": date}


@router.get("/settings")
async def settings_data():
    """Return app settings (secrets masked)."""
    def mask(val: str) -> str:
        if not val:
            return ""
        if len(val) <= 8:
            return "***"
        return val[:4] + "***" + val[-4:]

    return {
        "resend_api_key": mask(settings.resend_api_key),
        "from_email": settings.from_email,
        "telegram_bot_token": mask(settings.telegram_bot_token),
        "telegram_chat_id": settings.telegram_chat_id,
        "management_telegram_chat_id": settings.management_telegram_chat_id,
        "timezone": settings.timezone,
        "daily_brief_time": settings.daily_brief_time,
        "weekly_report_day": settings.weekly_report_day,
        "weekly_report_time": settings.weekly_report_time,
        "reminder_no_update_time": settings.reminder_no_update_time,
        "management_emails": settings.management_emails,
        "management_cc_emails": settings.management_cc_emails,
        "alert_emails": settings.alert_emails,
        "alert_cc_emails": settings.alert_cc_emails,
        "app_url": settings.app_url,
        "gemini_api_key": mask(settings.gemini_api_key),
    }
