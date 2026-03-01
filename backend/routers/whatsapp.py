from fastapi import APIRouter, Request, Response
from backend.database import get_db
from backend.services.ai_parser import parse_update
from backend.services.screenshot_processor import process_screenshots
from backend.utils.date_helpers import today_str
from backend.config import settings
from datetime import datetime
import httpx
import os
import uuid

router = APIRouter()

UPLOAD_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "uploads")


@router.post("/whatsapp/webhook")
async def whatsapp_webhook(request: Request):
    """Handle incoming WhatsApp messages from Twilio."""
    form_data = await request.form()

    incoming_msg = form_data.get("Body", "")
    num_media = int(form_data.get("NumMedia", 0))
    from_number = form_data.get("From", "")

    # Verify this is from our authorized user
    if settings.user_whatsapp and settings.user_whatsapp not in from_number:
        twiml = '<?xml version="1.0" encoding="UTF-8"?><Response><Message>Unauthorized.</Message></Response>'
        return Response(content=twiml, media_type="application/xml")

    db = get_db()
    date = today_str()

    # Handle special commands
    lower_msg = incoming_msg.strip().lower()
    if lower_msg == "status":
        return await _handle_status_command(db, date)
    if lower_msg == "help":
        return await _handle_help_command()

    # Download media (screenshots)
    screenshot_paths = []
    if num_media > 0:
        date_dir = os.path.join(UPLOAD_DIR, date)
        os.makedirs(date_dir, exist_ok=True)
        for i in range(num_media):
            media_url = form_data.get(f"MediaUrl{i}")
            media_type = form_data.get(f"MediaContentType{i}", "")
            if media_url and media_type.startswith("image/"):
                ext = ".jpg" if "jpeg" in media_type else ".png"
                filename = f"{uuid.uuid4().hex}{ext}"
                filepath = os.path.join(date_dir, filename)
                # Download from Twilio with auth
                async with httpx.AsyncClient() as client:
                    resp = await client.get(
                        media_url,
                        auth=(settings.twilio_account_sid, settings.twilio_auth_token),
                    )
                    if resp.status_code == 200:
                        with open(filepath, "wb") as f:
                            f.write(resp.content)
                        screenshot_paths.append(f"uploads/{date}/{filename}")

    # Process screenshots
    screenshot_text = ""
    if screenshot_paths:
        full_paths = [
            os.path.join(os.path.dirname(__file__), "..", "..", path)
            for path in screenshot_paths
        ]
        screenshot_text = await process_screenshots(full_paths)

    # Combine and parse
    combined_text = incoming_msg
    if screenshot_text:
        combined_text += f"\n\n[Screenshot content]: {screenshot_text}"

    projects = await db.projects.find({"status": "active"}).to_list(None)
    team_members = await db.team_members.find({"is_active": True}).to_list(None)

    parsed, confidence = await parse_update(combined_text, projects, team_members)

    # Store update
    update_doc = {
        "raw_text": incoming_msg,
        "source": "whatsapp",
        "has_screenshot": len(screenshot_paths) > 0,
        "screenshot_paths": screenshot_paths,
        "screenshot_extracted_text": screenshot_text,
        "parsed": parsed,
        "ai_confidence": confidence,
        "created_at": datetime.utcnow(),
        "date": date,
    }
    await db.updates.insert_one(update_doc)

    # Build acknowledgment
    ack_parts = ["Got it!"]
    team_updates = parsed.get("team_updates", [])
    if team_updates:
        names = set(t["team_member_name"] for t in team_updates)
        projects_mentioned = set(t["project_name"] for t in team_updates)
        ack_parts.append(
            f"Parsed: {', '.join(names)} on {', '.join(projects_mentioned)}."
        )
    action_items = parsed.get("action_items", [])
    if action_items:
        ack_parts.append(f"{len(action_items)} action item(s) noted.")
    blockers = parsed.get("blockers", [])
    if blockers:
        ack_parts.append(f"{len(blockers)} blocker(s) flagged.")

    reply_text = " ".join(ack_parts)

    twiml = f'<?xml version="1.0" encoding="UTF-8"?><Response><Message>{reply_text}</Message></Response>'
    return Response(content=twiml, media_type="application/xml")


@router.get("/whatsapp/webhook")
async def whatsapp_webhook_verify(request: Request):
    """Twilio webhook verification (GET)."""
    return Response(content="OK", media_type="text/plain")


async def _handle_status_command(db, date):
    """Return today's update summary."""
    count = await db.updates.count_documents({"date": date})
    if count == 0:
        text = "No updates submitted today yet."
    else:
        updates = await db.updates.find({"date": date}).to_list(None)
        total_team = sum(
            len(u.get("parsed", {}).get("team_updates", [])) for u in updates
        )
        total_actions = sum(
            len(u.get("parsed", {}).get("action_items", [])) for u in updates
        )
        total_blockers = sum(
            len(u.get("parsed", {}).get("blockers", [])) for u in updates
        )
        text = (
            f"Today's summary: {count} update(s), "
            f"{total_team} team activities, "
            f"{total_actions} action item(s), "
            f"{total_blockers} blocker(s)."
        )
    twiml = f'<?xml version="1.0" encoding="UTF-8"?><Response><Message>{text}</Message></Response>'
    return Response(content=twiml, media_type="application/xml")


async def _handle_help_command():
    """Return help text."""
    text = (
        "PM Update Tool - Commands:\n"
        "- Just type your update naturally\n"
        "- Send screenshots of chats/boards\n"
        "- 'status' - Today's summary\n"
        "- 'help' - This message"
    )
    twiml = f'<?xml version="1.0" encoding="UTF-8"?><Response><Message>{text}</Message></Response>'
    return Response(content=twiml, media_type="application/xml")
