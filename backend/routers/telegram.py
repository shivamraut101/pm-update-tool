"""Telegram webhook route + cron trigger endpoints for Render deployment."""
from fastapi import APIRouter, Request, HTTPException

from backend.config import settings
from backend.services.telegram_bot import handle_webhook_update, send_telegram_message
from backend.services.email_sender import send_email
from backend.utils.date_helpers import today_str, week_boundaries

router = APIRouter()


@router.post("/telegram/webhook")
async def telegram_webhook(request: Request):
    """Receive updates from Telegram via webhook."""
    update = await request.json()
    await handle_webhook_update(update)
    return {"ok": True}


# ---------------------------------------------------------------------------
# Cron trigger endpoints (called by cron-job.org or similar)
# ---------------------------------------------------------------------------

@router.post("/trigger/daily-report")
async def trigger_daily_report(request: Request):
    """Trigger daily brief generation + delivery. Secured by API key."""
    _verify_api_key(request)

    from backend.services.report_generator import generate_daily_brief
    from backend.services.email_sender import send_daily_brief_email

    date = today_str()
    report = await generate_daily_brief(date)
    if not report:
        return {"status": "skipped", "reason": "no updates today"}

    results = []

    # Send via Email
    emails = settings.get_management_emails_list()
    if emails:
        try:
            await send_daily_brief_email(report, emails)
            results.append(f"email:{','.join(emails)}")
        except Exception as e:
            results.append(f"email_error:{str(e)[:100]}")

    # Send to management via Telegram
    mgmt_chat_id = settings.management_telegram_chat_id
    if mgmt_chat_id:
        try:
            plain = report.get("content_plain") or report.get("content_markdown", "")
            await send_telegram_message(mgmt_chat_id, f"*Daily Brief - {date}*\n\n{plain}")
            results.append("telegram:management")
        except Exception as e:
            results.append(f"telegram_error:{str(e)[:100]}")

    # Notify PM (you) on Telegram
    if settings.telegram_chat_id:
        await send_telegram_message(
            settings.telegram_chat_id,
            "Daily brief generated & sent.\n" + "\n".join(f"- {r}" for r in results),
        )

    return {"status": "sent", "date": date, "channels": results}


@router.post("/trigger/weekly-report")
async def trigger_weekly_report(request: Request):
    """Trigger weekly report generation + delivery. Secured by API key."""
    _verify_api_key(request)

    from backend.services.report_generator import generate_weekly_report
    from backend.services.email_sender import send_weekly_report_email

    _, week_end = week_boundaries()
    report = await generate_weekly_report(week_end)
    if not report:
        return {"status": "skipped", "reason": "no daily reports this week"}

    results = []

    # Send via Email
    emails = settings.get_management_emails_list()
    if emails:
        try:
            await send_weekly_report_email(report, emails)
            results.append(f"email:{','.join(emails)}")
        except Exception as e:
            results.append(f"email_error:{str(e)[:100]}")

    # Send to management via Telegram
    mgmt_chat_id = settings.management_telegram_chat_id
    if mgmt_chat_id:
        try:
            plain = report.get("content_plain") or report.get("content_markdown", "")
            await send_telegram_message(mgmt_chat_id, f"*Weekly Report*\n\n{plain}")
            results.append("telegram:management")
        except Exception as e:
            results.append(f"telegram_error:{str(e)[:100]}")

    # Notify PM (you) on Telegram
    if settings.telegram_chat_id:
        await send_telegram_message(
            settings.telegram_chat_id,
            "Weekly report generated & sent.\n" + "\n".join(f"- {r}" for r in results),
        )

    return {"status": "sent", "week_end": week_end, "channels": results}


@router.post("/trigger/reminder-check")
async def trigger_reminder_check(request: Request):
    """Trigger reminder engine check. Secured by API key."""
    _verify_api_key(request)

    from backend.services.reminder_engine import run_reminder_check
    await run_reminder_check()
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# Test endpoints
# ---------------------------------------------------------------------------

@router.post("/test-email")
async def test_email():
    """Send a test email to verify SMTP configuration works."""
    if not settings.smtp_user or not settings.smtp_password:
        raise HTTPException(status_code=400, detail="SMTP not configured. Set SMTP_USER and SMTP_PASSWORD in .env")

    to_emails = settings.get_management_emails_list()
    if not to_emails:
        raise HTTPException(status_code=400, detail="No management emails configured. Set MANAGEMENT_EMAILS in .env")

    try:
        await send_email(
            to_emails=to_emails,
            subject="Test Email - PM Update Tool",
            html_body=(
                '<div style="font-family:sans-serif;padding:20px;">'
                '<h2 style="color:#4f46e5;">Test Successful!</h2>'
                '<p>Your SMTP email configuration is working correctly.</p>'
                '<hr style="border-color:#e5e7eb;">'
                '<small style="color:#9ca3af;">Sent from PM Update Tool</small>'
                '</div>'
            ),
            plain_body="Test Successful! Your SMTP email configuration is working correctly.",
        )
        return {"status": "sent", "to": to_emails}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Email failed: {str(e)}")


# ---------------------------------------------------------------------------
# Health check (use with cron-job.org to keep Render awake)
# ---------------------------------------------------------------------------

@router.get("/health")
async def health_check():
    """Health check endpoint — use cron-job.org to ping every 5 min."""
    return {"status": "ok", "service": "pm-update-tool"}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _verify_api_key(request: Request):
    """Check X-API-Key header or ?key= query param."""
    key = request.headers.get("x-api-key") or request.query_params.get("key")
    if not key or key != settings.api_key:
        raise HTTPException(status_code=401, detail="Invalid API key")
