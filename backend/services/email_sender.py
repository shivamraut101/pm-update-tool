import resend
from datetime import datetime

from backend.config import settings
from backend.database import get_db
from backend.utils.logger import get_logger

logger = get_logger(__name__)


async def send_email(
    to_emails: list,
    subject: str,
    html_body: str,
    plain_body: str,
    cc_emails: list = None,
):
    """Send an email via Resend API with optional CC."""
    if not settings.resend_api_key:
        logger.warning("Email not configured (no RESEND_API_KEY) - skipping send")
        return

    resend.api_key = settings.resend_api_key

    params = {
        "from": f"PM Update Tool <{settings.from_email}>" if settings.from_email else "PM Update Tool <noreply@resend.dev>",
        "to": to_emails,
        "subject": subject,
        "html": html_body,
        "text": plain_body,
    }

    if settings.from_email:
        params["reply_to"] = settings.from_email

    if cc_emails:
        params["cc"] = cc_emails

    try:
        result = resend.Emails.send(params)
        all_recipients = list(to_emails) + (cc_emails or [])
        logger.info(f"Successfully sent to {all_recipients} (id: {result.get('id', 'unknown')})")
    except Exception as e:
        error_type = type(e).__name__
        error_msg = str(e)
        logger.error(f"Resend error: {error_type}: {error_msg}")
        raise


async def send_daily_brief_email(report: dict, to_emails: list):
    """Send a daily brief report via email to management (with CC)."""
    if not to_emails:
        return
    subject = f"Daily Project Brief - {report['date']}"
    cc = settings.get_management_cc_list()
    await send_email(
        to_emails=to_emails,
        subject=subject,
        html_body=report.get("content_html", ""),
        plain_body=report.get("content_markdown", ""),
        cc_emails=cc,
    )
    # Update delivery status
    db = get_db()
    await db.reports.update_one(
        {"_id": report["_id"]},
        {"$set": {
            "delivery_status.email.sent": True,
            "delivery_status.email.sent_at": datetime.utcnow(),
        }},
    )


async def send_weekly_report_email(report: dict, to_emails: list):
    """Send a weekly report via email to management (with CC)."""
    if not to_emails:
        return
    subject = f"Weekly Project Summary - {report.get('week_start', '')} to {report.get('week_end', '')}"
    cc = settings.get_management_cc_list()
    await send_email(
        to_emails=to_emails,
        subject=subject,
        html_body=report.get("content_html", ""),
        plain_body=report.get("content_markdown", ""),
        cc_emails=cc,
    )
    db = get_db()
    await db.reports.update_one(
        {"_id": report["_id"]},
        {"$set": {
            "delivery_status.email.sent": True,
            "delivery_status.email.sent_at": datetime.utcnow(),
        }},
    )


async def send_alert_email(subject: str, message: str):
    """Send an alert/reminder email to the user themselves (with CC)."""
    to_emails = settings.get_alert_emails_list()
    if not to_emails:
        return
    cc = settings.get_alert_cc_list()
    html_body = f"""<div style="font-family: sans-serif; padding: 20px;">
    <h2 style="color: #d97706;">PM Update Tool - Alert</h2>
    <p>{message}</p>
    <hr style="border-color: #e5e7eb;">
    <small style="color: #9ca3af;">This is an automated alert from PM Update Tool</small>
    </div>"""
    await send_email(
        to_emails=to_emails,
        subject=f"[PM Alert] {subject}",
        html_body=html_body,
        plain_body=message,
        cc_emails=cc,
    )
