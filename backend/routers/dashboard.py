from fastapi import APIRouter, Request
from fastapi.templating import Jinja2Templates
import os

from backend.database import get_db
from backend.utils.date_helpers import today_str

router = APIRouter()

templates_dir = os.path.join(os.path.dirname(__file__), "..", "..", "frontend", "templates")
templates = Jinja2Templates(directory=templates_dir)


@router.get("/")
async def dashboard_page(request: Request):
    """Main dashboard page."""
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

    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "today_updates": today_updates,
            "active_projects": active_projects,
            "active_members": active_members,
            "active_reminders": active_reminders,
            "recent_updates": recent_updates,
            "blockers": blockers,
            "action_items": action_items,
            "last_report": last_report,
            "date": date,
        },
    )


@router.get("/chat")
async def chat_page(request: Request):
    """Chat-style input page."""
    db = get_db()
    date = today_str()
    today_updates = await db.updates.find({"date": date}).sort("created_at", -1).to_list(50)
    for u in today_updates:
        u["_id"] = str(u["_id"])
    return templates.TemplateResponse(
        "chat_input.html",
        {"request": request, "updates": today_updates, "date": date},
    )


@router.get("/projects-page")
async def projects_page(request: Request):
    """Projects management page."""
    db = get_db()
    projects = await db.projects.find().sort("name", 1).to_list(None)
    for p in projects:
        p["_id"] = str(p["_id"])
    return templates.TemplateResponse(
        "projects.html",
        {"request": request, "projects": projects},
    )


@router.get("/team-page")
async def team_page(request: Request):
    """Team members management page."""
    db = get_db()
    members = await db.team_members.find().sort("name", 1).to_list(None)
    for m in members:
        m["_id"] = str(m["_id"])
    projects = await db.projects.find({"status": "active"}).to_list(None)
    for p in projects:
        p["_id"] = str(p["_id"])
    return templates.TemplateResponse(
        "team.html",
        {"request": request, "members": members, "projects": projects},
    )


@router.get("/reports-page")
async def reports_page(request: Request):
    """Reports history page."""
    db = get_db()
    reports = await db.reports.find().sort("created_at", -1).to_list(50)
    for r in reports:
        r["_id"] = str(r["_id"])
    return templates.TemplateResponse(
        "reports.html",
        {"request": request, "reports": reports},
    )


@router.get("/reminders-page")
async def reminders_page(request: Request):
    """Reminders page."""
    db = get_db()
    active = await db.reminders.find({"is_dismissed": False}).sort("trigger_time", -1).to_list(None)
    dismissed = await db.reminders.find({"is_dismissed": True}).sort("trigger_time", -1).to_list(20)
    for r in active + dismissed:
        r["_id"] = str(r["_id"])
    return templates.TemplateResponse(
        "reminders.html",
        {"request": request, "active_reminders": active, "dismissed_reminders": dismissed},
    )


@router.get("/settings-page")
async def settings_page(request: Request):
    """Settings page."""
    from backend.config import settings as app_settings
    return templates.TemplateResponse(
        "settings.html",
        {"request": request, "settings": app_settings},
    )
