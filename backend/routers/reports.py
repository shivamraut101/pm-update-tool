from fastapi import APIRouter, HTTPException
from typing import Optional
from bson import ObjectId

from backend.database import get_db
from backend.services.report_generator import generate_daily_brief, generate_weekly_report
from backend.services.email_sender import send_daily_brief_email, send_weekly_report_email
from backend.services.telegram_bot import send_telegram_message
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
    try:
        report = await generate_daily_brief(target_date)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Report generation failed: {str(e)}")
    if report:
        report["_id"] = str(report["_id"])
    return report or {"message": "No updates found for this date"}


@router.post("/reports/generate/weekly")
async def trigger_weekly_report():
    """Manually trigger weekly report generation."""
    _, week_end = week_boundaries()
    try:
        report = await generate_weekly_report(week_end)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Weekly report generation failed: {str(e)}")
    if report:
        report["_id"] = str(report["_id"])
    return report or {"message": "No daily reports found for this week"}


@router.post("/reports/{report_id}/send")
async def resend_report(report_id: str, channel: str = "both"):
    """Re-send a report via email and/or Telegram."""
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

    if channel in ("both", "telegram"):
        mgmt_chat_id = settings.management_telegram_chat_id
        if mgmt_chat_id:
            try:
                plain = report.get("content_plain") or report.get("content_markdown", "")
                label = "Daily Brief" if report["type"] == "daily" else "Weekly Report"
                await send_telegram_message(mgmt_chat_id, f"*{label}*\n\n{plain}")
                results["telegram"] = "sent"
            except Exception as e:
                results["telegram"] = f"failed: {str(e)}"
        else:
            results["telegram"] = "skipped: no management chat ID configured"

    return results
