import aiosmtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime

from backend.config import settings
from backend.database import get_db


async def send_email(
    to_emails: list,
    subject: str,
    html_body: str,
    plain_body: str,
    cc_emails: list = None,
):
    """Send an email via SMTP with optional CC."""
    if not settings.smtp_user or not settings.smtp_password:
        print("Email not configured - skipping send")
        return

    msg = MIMEMultipart("alternative")
    msg["From"] = settings.from_email or settings.smtp_user
    msg["To"] = ", ".join(to_emails)
    msg["Subject"] = subject

    if cc_emails:
        msg["Cc"] = ", ".join(cc_emails)

    msg.attach(MIMEText(plain_body, "plain"))
    msg.attach(MIMEText(html_body, "html"))

    # All recipients (To + CC) must be in the recipients list for SMTP
    all_recipients = list(to_emails)
    if cc_emails:
        all_recipients.extend(cc_emails)

    try:
        await aiosmtplib.send(
            msg,
            hostname=settings.smtp_host,
            port=settings.smtp_port,
            start_tls=True,
            username=settings.smtp_user,
            password=settings.smtp_password,
            recipients=all_recipients,
            timeout=30,  # 30 second timeout
        )
        print(f"[email] Successfully sent to {all_recipients}")
    except Exception as e:
        error_type = type(e).__name__
        error_msg = str(e)
        print(f"[email] SMTP error: {error_type}: {error_msg}")
        print(f"[email] Config: {settings.smtp_host}:{settings.smtp_port}, user={settings.smtp_user}")
        raise  # Re-raise so caller can handle it


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
