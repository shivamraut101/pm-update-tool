from fastapi import APIRouter, HTTPException
from typing import Optional
from bson import ObjectId

from backend.database import get_db
from backend.services.report_generator import generate_daily_brief, generate_weekly_report
from backend.services.email_sender import send_daily_brief_email, send_weekly_report_email
from backend.services.whatsapp_sender import send_report_whatsapp
from backend.utils.date_helpers import today_str, week_boundaries
from backend.config import settings

router = APIRouter()


@router.get("/reports")
async def list_reports(
    type: Optional[str] = None,
    limit: int = 20,
    skip: int = 0,
):
    """List generated reports."""
    db = get_db()
    query = {}
    if type:
        query["type"] = type
    reports = await db.reports.find(query).sort("created_at", -1).skip(skip).limit(limit).to_list(length=limit)
    for r in reports:
        r["_id"] = str(r["_id"])
    return reports


@router.get("/reports/{report_id}")
async def get_report(report_id: str):
    """Get full report content."""
    db = get_db()
    report = await db.reports.find_one({"_id": ObjectId(report_id)})
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    report["_id"] = str(report["_id"])
    return report


@router.post("/reports/generate/daily")
async def trigger_daily_report(date: Optional[str] = None):
    """Manually trigger daily brief generation."""
    target_date = date or today_str()
    report = await generate_daily_brief(target_date)
    if report:
        report["_id"] = str(report["_id"])
    return report or {"message": "No updates found for this date"}


@router.post("/reports/generate/weekly")
async def trigger_weekly_report():
    """Manually trigger weekly report generation."""
    _, week_end = week_boundaries()
    report = await generate_weekly_report(week_end)
    if report:
        report["_id"] = str(report["_id"])
    return report or {"message": "No daily reports found for this week"}


@router.post("/reports/{report_id}/send")
async def resend_report(report_id: str, channel: str = "both"):
    """Re-send a report via email and/or WhatsApp."""
    db = get_db()
    report = await db.reports.find_one({"_id": ObjectId(report_id)})
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")

    results = {}

    if channel in ("both", "email"):
        try:
            emails = settings.get_management_emails_list()
            if report["type"] == "daily":
                await send_daily_brief_email(report, emails)
            else:
                await send_weekly_report_email(report, emails)
            results["email"] = "sent"
        except Exception as e:
            results["email"] = f"failed: {str(e)}"

    if channel in ("both", "whatsapp"):
        try:
            numbers = settings.get_management_whatsapp_list()
            await send_report_whatsapp(report, numbers)
            results["whatsapp"] = "sent"
        except Exception as e:
            results["whatsapp"] = f"failed: {str(e)}"

    return results
