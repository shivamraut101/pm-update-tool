import base64
import os
import tempfile
from datetime import datetime

from fastapi import APIRouter, Request

from backend.config import settings
from backend.database import get_db
from backend.services.ai_parser import parse_update
from backend.services.screenshot_processor import process_screenshots
from backend.utils.date_helpers import today_str

router = APIRouter()


@router.post("/whatsapp/incoming")
async def whatsapp_incoming(request: Request):
    """Handle incoming WhatsApp messages forwarded by the Node.js bridge."""
    data = await request.json()

    incoming_msg = data.get("text", "")
    from_number = data.get("from_number", "")
    has_media = data.get("has_media", False)
    media = data.get("media")

    # Verify authorized user
    if settings.user_whatsapp:
        clean_number = settings.user_whatsapp.replace("+", "")
        if clean_number not in from_number:
            return {"reply": "Unauthorized."}

    db = get_db()
    date = today_str()

    # Handle special commands
    lower_msg = incoming_msg.strip().lower()
    if lower_msg == "status":
        return await _handle_status_command(db, date)
    if lower_msg == "help":
        return _handle_help_command()

    # Process screenshot via temp file (extract text, then delete)
    screenshot_text = ""
    if has_media and media:
        img_data = base64.b64decode(media.get("data", ""))
        if img_data:
            screenshot_text = await _extract_and_cleanup_screenshot(img_data)

    # Combine text and screenshot content
    combined_text = incoming_msg
    if screenshot_text:
        combined_text += f"\n\n[Screenshot content]: {screenshot_text}"

    # Parse with AI
    projects = await db.projects.find({"status": "active"}).to_list(None)
    team_members = await db.team_members.find({"is_active": True}).to_list(None)

    parsed, confidence = await parse_update(combined_text, projects, team_members)

    # Store update (no file paths — just extracted text)
    update_doc = {
        "raw_text": incoming_msg,
        "source": "whatsapp",
        "has_screenshot": bool(screenshot_text),
        "screenshot_paths": [],
        "screenshot_extracted_text": screenshot_text,
        "parsed": parsed,
        "ai_confidence": confidence,
        "created_at": datetime.utcnow(),
        "date": date,
    }
    await db.updates.insert_one(update_doc)

    # Build acknowledgment reply
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
    return {"reply": reply_text}


@router.get("/whatsapp/status")
async def whatsapp_bridge_status():
    """Check WhatsApp bridge connection status."""
    import httpx
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{settings.whatsapp_bridge_url}/health",
                timeout=5.0,
            )
            return resp.json()
    except Exception as e:
        return {"status": "disconnected", "error": str(e)}


# ---------------------------------------------------------------------------
# Screenshot temp-file processing (same pattern as telegram_bot.py)
# ---------------------------------------------------------------------------

async def _extract_and_cleanup_screenshot(photo_data: bytes) -> str:
    """Save photo to temp file, extract text with AI, then delete the file."""
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
            tmp.write(photo_data)
            tmp_path = tmp.name
        extracted = await process_screenshots([tmp_path])
        return extracted
    except Exception as e:
        print(f"[whatsapp] Screenshot extraction error: {e}")
        return ""
    finally:
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except Exception:
                pass


# ---------------------------------------------------------------------------
# Command handlers
# ---------------------------------------------------------------------------

async def _handle_status_command(db, date):
    count = await db.updates.count_documents({"date": date})
    if count == 0:
        return {"reply": "No updates submitted today yet."}

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
    return {
        "reply": (
            f"Today's summary: {count} update(s), "
            f"{total_team} team activities, "
            f"{total_actions} action item(s), "
            f"{total_blockers} blocker(s)."
        )
    }


def _handle_help_command():
    return {
        "reply": (
            "PM Update Tool - Commands:\n"
            "- Just type your update naturally\n"
            "- Send screenshots of chats/boards\n"
            "- 'status' - Today's summary\n"
            "- 'help' - This message"
        )
    }
