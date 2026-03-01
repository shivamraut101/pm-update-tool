from datetime import datetime
from twilio.rest import Client

from backend.config import settings
from backend.database import get_db
from backend.utils.text_formatters import markdown_to_whatsapp, truncate_text


def _get_twilio_client():
    if not settings.twilio_account_sid or not settings.twilio_auth_token:
        return None
    return Client(settings.twilio_account_sid, settings.twilio_auth_token)


async def send_whatsapp_message(to_number: str, text: str):
    """Send a single WhatsApp message via Twilio."""
    client = _get_twilio_client()
    if not client:
        print("Twilio not configured - skipping WhatsApp send")
        return

    chunks = truncate_text(text, max_length=1500)
    for i, chunk in enumerate(chunks):
        if len(chunks) > 1:
            chunk = f"[{i + 1}/{len(chunks)}]\n{chunk}"
        client.messages.create(
            body=chunk,
            from_=settings.twilio_whatsapp_from,
            to=f"whatsapp:{to_number}" if not to_number.startswith("whatsapp:") else to_number,
        )


async def send_report_whatsapp(report: dict, to_numbers: list):
    """Send a report to all management WhatsApp numbers."""
    if not to_numbers:
        return

    # Convert markdown to WhatsApp format
    plain_text = report.get("content_plain", "") or report.get("content_markdown", "")
    whatsapp_text = markdown_to_whatsapp(plain_text)

    for number in to_numbers:
        try:
            await send_whatsapp_message(number, whatsapp_text)
        except Exception as e:
            print(f"WhatsApp send error to {number}: {e}")

    # Update delivery status
    db = get_db()
    await db.reports.update_one(
        {"_id": report["_id"]},
        {"$set": {
            "delivery_status.whatsapp.sent": True,
            "delivery_status.whatsapp.sent_at": datetime.utcnow(),
        }},
    )


async def send_reminder_whatsapp(message: str):
    """Send a reminder to the user's own WhatsApp."""
    if settings.user_whatsapp:
        await send_whatsapp_message(settings.user_whatsapp, f"Reminder: {message}")
