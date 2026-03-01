from datetime import datetime
import httpx

from backend.config import settings
from backend.database import get_db
from backend.utils.text_formatters import markdown_to_whatsapp, truncate_text


async def _bridge_available() -> bool:
    """Check if the WhatsApp bridge is running and ready."""
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{settings.whatsapp_bridge_url}/health",
                timeout=5.0,
            )
            data = resp.json()
            return data.get("status") == "ready"
    except Exception:
        return False


async def send_whatsapp_message(to_number: str, text: str):
    """Send a single WhatsApp message via the bridge."""
    if not await _bridge_available():
        print("WhatsApp bridge not available - skipping send")
        return

    chunks = truncate_text(text, max_length=4000)
    for i, chunk in enumerate(chunks):
        if len(chunks) > 1:
            chunk = f"[{i + 1}/{len(chunks)}]\n{chunk}"
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    f"{settings.whatsapp_bridge_url}/send",
                    json={"to": to_number, "message": chunk},
                    timeout=30.0,
                )
                if resp.status_code != 200:
                    print(f"WhatsApp send failed: {resp.text}")
        except Exception as e:
            print(f"WhatsApp send error: {e}")


async def send_report_whatsapp(report: dict, to_numbers: list):
    """Send a report to all management WhatsApp numbers."""
    if not to_numbers:
        return

    plain_text = report.get("content_plain", "") or report.get("content_markdown", "")
    whatsapp_text = markdown_to_whatsapp(plain_text)

    for number in to_numbers:
        try:
            await send_whatsapp_message(number, whatsapp_text)
        except Exception as e:
            print(f"WhatsApp send error to {number}: {e}")

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
