import aiosmtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime

from backend.config import settings
from backend.database import get_db


async def send_email(to_emails: list, subject: str, html_body: str, plain_body: str):
    """Send an email via SMTP."""
    if not settings.smtp_user or not settings.smtp_password:
        print("Email not configured - skipping send")
        return

    msg = MIMEMultipart("alternative")
    msg["From"] = settings.from_email or settings.smtp_user
    msg["To"] = ", ".join(to_emails)
    msg["Subject"] = subject

    msg.attach(MIMEText(plain_body, "plain"))
    msg.attach(MIMEText(html_body, "html"))

    await aiosmtplib.send(
        msg,
        hostname=settings.smtp_host,
        port=settings.smtp_port,
        start_tls=True,
        username=settings.smtp_user,
        password=settings.smtp_password,
    )


async def send_daily_brief_email(report: dict, to_emails: list):
    """Send a daily brief report via email."""
    if not to_emails:
        return
    subject = f"Daily Project Brief - {report['date']}"
    await send_email(
        to_emails=to_emails,
        subject=subject,
        html_body=report.get("content_html", ""),
        plain_body=report.get("content_markdown", ""),
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
    """Send a weekly report via email."""
    if not to_emails:
        return
    subject = f"Weekly Project Summary - {report.get('week_start', '')} to {report.get('week_end', '')}"
    await send_email(
        to_emails=to_emails,
        subject=subject,
        html_body=report.get("content_html", ""),
        plain_body=report.get("content_markdown", ""),
    )
    db = get_db()
    await db.reports.update_one(
        {"_id": report["_id"]},
        {"$set": {
            "delivery_status.email.sent": True,
            "delivery_status.email.sent_at": datetime.utcnow(),
        }},
    )
