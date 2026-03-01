"""Telegram bot for receiving project updates."""
import asyncio
import os
import uuid
import base64
from datetime import datetime

import httpx

from backend.config import settings
from backend.database import get_db
from backend.services.ai_parser import parse_update
from backend.services.screenshot_processor import process_screenshots
from backend.utils.date_helpers import today_str

UPLOAD_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "uploads")

# Telegram Bot API base URL
_bot_token = ""
_base_url = ""
_authorized_chat_id = ""
_running = False
_offset = 0


def configure_telegram(bot_token: str, authorized_chat_id: str = ""):
    global _bot_token, _base_url, _authorized_chat_id
    _bot_token = bot_token
    _base_url = f"https://api.telegram.org/bot{bot_token}"
    _authorized_chat_id = authorized_chat_id


async def send_telegram_message(chat_id: str, text: str):
    """Send a message to a Telegram chat."""
    if not _bot_token:
        print("[telegram] Bot token not configured")
        return
    async with httpx.AsyncClient() as client:
        await client.post(
            f"{_base_url}/sendMessage",
            json={"chat_id": chat_id, "text": text, "parse_mode": "Markdown"},
            timeout=30.0,
        )


async def _get_updates(offset: int = 0, timeout: int = 30):
    """Long-poll for new messages from Telegram."""
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{_base_url}/getUpdates",
                params={"offset": offset, "timeout": timeout},
                timeout=timeout + 10,
            )
            if resp.status_code == 200:
                data = resp.json()
                if data.get("ok"):
                    return data.get("result", [])
    except Exception as e:
        print(f"[telegram] Polling error: {e}")
        await asyncio.sleep(5)
    return []


async def _download_photo(file_id: str) -> bytes | None:
    """Download a photo from Telegram servers."""
    try:
        async with httpx.AsyncClient() as client:
            # Get file path
            resp = await client.get(
                f"{_base_url}/getFile",
                params={"file_id": file_id},
                timeout=15.0,
            )
            data = resp.json()
            if not data.get("ok"):
                return None
            file_path = data["result"]["file_path"]

            # Download the file
            resp = await client.get(
                f"https://api.telegram.org/file/bot{_bot_token}/{file_path}",
                timeout=30.0,
            )
            if resp.status_code == 200:
                return resp.content
    except Exception as e:
        print(f"[telegram] Photo download error: {e}")
    return None


async def _handle_message(message: dict):
    """Process an incoming Telegram message."""
    chat_id = str(message["chat"]["id"])

    # Check authorization
    if _authorized_chat_id and chat_id != _authorized_chat_id:
        await send_telegram_message(chat_id, "Unauthorized. Your chat ID: " + chat_id)
        return

    text = message.get("text", "") or message.get("caption", "") or ""

    # Handle commands
    lower_text = text.strip().lower()
    if lower_text == "/start":
        await send_telegram_message(
            chat_id,
            "*PM Update Tool Bot*\n\n"
            "Send me your daily updates naturally. I'll parse them and track everything.\n\n"
            "*Commands:*\n"
            "/status - Quick counts for today\n"
            "/today - Detailed view of all parsed updates\n"
            "/pending - Team members with no updates today\n"
            "/report - Generate & send daily brief NOW\n"
            "/week - Generate & send weekly report NOW\n"
            "/undo - Delete your last update\n"
            "/help - Show commands\n\n"
            "Just type your updates, e.g.:\n"
            "_Yash fixed the login bug on B2B Portal. Shobhit pushed API docs PR._\n\n"
            f"Your chat ID: `{chat_id}`",
        )
        return

    if lower_text in ("/help", "help"):
        await send_telegram_message(
            chat_id,
            "*PM Update Tool - Commands:*\n\n"
            "*Input:*\n"
            "- Type your update naturally\n"
            "- Send screenshots of chats/boards\n\n"
            "*Review:*\n"
            "/status - Quick counts (updates, activities, blockers)\n"
            "/today - Detailed parsed updates (who did what)\n"
            "/pending - Team members missing from today's updates\n\n"
            "*Actions:*\n"
            "/report - Generate & send daily brief to management\n"
            "/week - Generate & send weekly report to management\n"
            "/undo - Delete your last submitted update",
        )
        return

    if lower_text in ("/status", "status"):
        db = get_db()
        date = today_str()
        count = await db.updates.count_documents({"date": date})
        if count == 0:
            await send_telegram_message(chat_id, "No updates submitted today yet.")
            return
        updates = await db.updates.find({"date": date}).to_list(None)
        total_team = sum(len(u.get("parsed", {}).get("team_updates", [])) for u in updates)
        total_actions = sum(len(u.get("parsed", {}).get("action_items", [])) for u in updates)
        total_blockers = sum(len(u.get("parsed", {}).get("blockers", [])) for u in updates)
        await send_telegram_message(
            chat_id,
            f"*Today's summary:*\n"
            f"- {count} update(s) submitted\n"
            f"- {total_team} team activities\n"
            f"- {total_actions} action item(s)\n"
            f"- {total_blockers} blocker(s)",
        )
        return

    if lower_text == "/today":
        await _cmd_today(chat_id)
        return

    if lower_text == "/pending":
        await _cmd_pending(chat_id)
        return

    if lower_text == "/report":
        await _cmd_report(chat_id)
        return

    if lower_text == "/week":
        await _cmd_week(chat_id)
        return

    if lower_text == "/undo":
        await _cmd_undo(chat_id)
        return

    # Process as an update
    await send_telegram_message(chat_id, "Processing your update...")

    # Handle photos
    screenshot_paths = []
    if "photo" in message:
        # Telegram sends multiple sizes, get the largest
        photo = message["photo"][-1]
        photo_data = await _download_photo(photo["file_id"])
        if photo_data:
            date = today_str()
            date_dir = os.path.join(UPLOAD_DIR, date)
            os.makedirs(date_dir, exist_ok=True)
            filename = f"{uuid.uuid4().hex}.jpg"
            filepath = os.path.join(date_dir, filename)
            with open(filepath, "wb") as f:
                f.write(photo_data)
            screenshot_paths.append(f"uploads/{date}/{filename}")

    # Process screenshots with AI
    screenshot_text = ""
    if screenshot_paths:
        full_paths = [
            os.path.join(os.path.dirname(__file__), "..", "..", path)
            for path in screenshot_paths
        ]
        screenshot_text = await process_screenshots(full_paths)

    combined_text = text
    if screenshot_text:
        combined_text += f"\n\n[Screenshot content]: {screenshot_text}"

    if not combined_text.strip():
        await send_telegram_message(chat_id, "No text or image content to process.")
        return

    # Parse with AI
    db = get_db()
    date = today_str()
    projects = await db.projects.find({"status": "active"}).to_list(None)
    team_members = await db.team_members.find({"is_active": True}).to_list(None)

    try:
        parsed, confidence = await parse_update(combined_text, projects, team_members)
    except Exception as e:
        await send_telegram_message(chat_id, f"AI parsing error: {str(e)[:200]}")
        return

    # Store update
    update_doc = {
        "raw_text": text,
        "source": "telegram",
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
        ack_parts.append(f"*Parsed:* {', '.join(names)} on {', '.join(projects_mentioned)}.")
    action_items = parsed.get("action_items", [])
    if action_items:
        ack_parts.append(f"{len(action_items)} action item(s) noted.")
    blockers = parsed.get("blockers", [])
    if blockers:
        ack_parts.append(f"{len(blockers)} blocker(s) flagged.")

    await send_telegram_message(chat_id, " ".join(ack_parts))


async def _cmd_today(chat_id: str):
    """Show detailed parsed updates for today."""
    db = get_db()
    date = today_str()
    updates = await db.updates.find({"date": date}).to_list(None)

    if not updates:
        await send_telegram_message(chat_id, "No updates submitted today yet.")
        return

    lines = [f"*Today's Updates ({date}):*\n"]

    # Group by project
    from collections import defaultdict
    by_project = defaultdict(list)

    for u in updates:
        for tu in u.get("parsed", {}).get("team_updates", []):
            proj = tu.get("project_name", "Unassigned")
            by_project[proj].append(tu)

    if by_project:
        for proj, team_updates in sorted(by_project.items()):
            lines.append(f"\n*{proj}*")
            for tu in team_updates:
                name = tu.get("team_member_name", "Unknown")
                summary = tu.get("summary", "")
                status = tu.get("status", "").upper()
                lines.append(f"  - {name}: {summary} [{status}]")
    else:
        lines.append("No team activities parsed yet.")

    # Action items
    all_actions = []
    for u in updates:
        all_actions.extend(u.get("parsed", {}).get("action_items", []))
    if all_actions:
        lines.append(f"\n*Action Items ({len(all_actions)}):*")
        for ai in all_actions:
            priority = ai.get("priority", "medium").upper()
            lines.append(f"  - [{priority}] {ai.get('description', '')} -> {ai.get('assigned_to', 'self')}")

    # Blockers
    all_blockers = []
    for u in updates:
        all_blockers.extend(u.get("parsed", {}).get("blockers", []))
    if all_blockers:
        lines.append(f"\n*Blockers ({len(all_blockers)}):*")
        for b in all_blockers:
            severity = b.get("severity", "medium").upper()
            lines.append(f"  - [{severity}] {b.get('project_name', '')}: {b.get('description', '')}")

    await send_telegram_message(chat_id, "\n".join(lines))


async def _cmd_pending(chat_id: str):
    """Show team members with no updates today."""
    db = get_db()
    date = today_str()

    # Get all active team members
    all_members = await db.team_members.find({"is_active": True}).to_list(None)

    # Get today's updates and extract mentioned team members
    updates = await db.updates.find({"date": date}).to_list(None)
    mentioned_ids = set()
    mentioned_names = set()
    for u in updates:
        for tu in u.get("parsed", {}).get("team_updates", []):
            if tu.get("team_member_id"):
                mentioned_ids.add(tu["team_member_id"])
            mentioned_names.add(tu.get("team_member_name", "").lower())

    # Find who's missing
    missing = []
    covered = []
    for m in all_members:
        mid = str(m["_id"])
        name = m["name"]
        if mid in mentioned_ids or name.lower() in mentioned_names:
            covered.append(name)
        else:
            missing.append(name)

    lines = [f"*Team Coverage for {date}:*\n"]

    if covered:
        lines.append(f"*Covered ({len(covered)}):*")
        for name in sorted(covered):
            lines.append(f"  + {name}")

    if missing:
        lines.append(f"\n*Missing ({len(missing)}):*")
        for name in sorted(missing):
            lines.append(f"  - {name}")
    else:
        lines.append("\nAll team members covered!")

    await send_telegram_message(chat_id, "\n".join(lines))


async def _cmd_report(chat_id: str):
    """Generate and send daily brief to management NOW."""
    await send_telegram_message(chat_id, "Generating daily brief...")

    from backend.services.report_generator import generate_daily_brief
    from backend.services.email_sender import send_daily_brief_email
    from backend.services.whatsapp_sender import send_report_whatsapp

    date = today_str()
    report = await generate_daily_brief(date)

    if not report:
        await send_telegram_message(chat_id, "No updates today - nothing to generate.")
        return

    delivery_results = []

    # Send email
    emails = settings.get_management_emails_list()
    if emails:
        try:
            await send_daily_brief_email(report, emails)
            delivery_results.append(f"Email sent to {', '.join(emails)}")
        except Exception as e:
            delivery_results.append(f"Email failed: {str(e)[:100]}")

    # Send WhatsApp
    numbers = settings.get_management_whatsapp_list()
    if numbers:
        try:
            await send_report_whatsapp(report, numbers)
            delivery_results.append(f"WhatsApp sent to {', '.join(numbers)}")
        except Exception as e:
            delivery_results.append(f"WhatsApp failed: {str(e)[:100]}")

    status_lines = ["*Daily brief generated & sent!*\n"]
    for r in delivery_results:
        status_lines.append(f"- {r}")

    if not delivery_results:
        status_lines.append("- Report saved but no delivery channels configured")

    await send_telegram_message(chat_id, "\n".join(status_lines))


async def _cmd_week(chat_id: str):
    """Generate and send weekly report to management NOW."""
    await send_telegram_message(chat_id, "Generating weekly report (using Pro AI for best quality)...")

    from backend.services.report_generator import generate_weekly_report
    from backend.services.email_sender import send_weekly_report_email
    from backend.services.whatsapp_sender import send_report_whatsapp
    from backend.utils.date_helpers import week_boundaries

    _, week_end = week_boundaries()
    report = await generate_weekly_report(week_end)

    if not report:
        await send_telegram_message(chat_id, "No daily reports found this week - nothing to synthesize.")
        return

    delivery_results = []

    # Send email
    emails = settings.get_management_emails_list()
    if emails:
        try:
            await send_weekly_report_email(report, emails)
            delivery_results.append(f"Email sent to {', '.join(emails)}")
        except Exception as e:
            delivery_results.append(f"Email failed: {str(e)[:100]}")

    # Send WhatsApp
    numbers = settings.get_management_whatsapp_list()
    if numbers:
        try:
            await send_report_whatsapp(report, numbers)
            delivery_results.append(f"WhatsApp sent to {', '.join(numbers)}")
        except Exception as e:
            delivery_results.append(f"WhatsApp failed: {str(e)[:100]}")

    status_lines = ["*Weekly report generated & sent!*\n"]
    for r in delivery_results:
        status_lines.append(f"- {r}")

    if not delivery_results:
        status_lines.append("- Report saved but no delivery channels configured")

    await send_telegram_message(chat_id, "\n".join(status_lines))


async def _cmd_undo(chat_id: str):
    """Delete the last submitted update."""
    db = get_db()
    date = today_str()

    # Find the most recent update from today
    last_update = await db.updates.find_one(
        {"date": date, "source": {"$in": ["telegram", "web"]}},
        sort=[("created_at", -1)],
    )

    if not last_update:
        await send_telegram_message(chat_id, "No updates today to undo.")
        return

    # Build preview of what we're deleting
    raw = last_update.get("raw_text", "")[:100]
    team_updates = last_update.get("parsed", {}).get("team_updates", [])
    preview = raw if raw else f"{len(team_updates)} team update(s)"

    # Delete it
    await db.updates.delete_one({"_id": last_update["_id"]})

    await send_telegram_message(
        chat_id,
        f"*Deleted last update:*\n_{preview}_\n\nSend /today to review remaining updates.",
    )


async def start_polling():
    """Start long-polling loop for Telegram updates."""
    global _running, _offset
    if not _bot_token:
        print("[telegram] Bot token not configured - Telegram bot disabled.")
        return

    _running = True
    print(f"[telegram] Bot started polling...")

    # Get bot info
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{_base_url}/getMe", timeout=10.0)
            data = resp.json()
            if data.get("ok"):
                bot_name = data["result"].get("username", "unknown")
                print(f"[telegram] Bot: @{bot_name}")
    except Exception as e:
        print(f"[telegram] Could not get bot info: {e}")

    while _running:
        try:
            updates = await _get_updates(offset=_offset, timeout=30)
            for update in updates:
                _offset = update["update_id"] + 1
                if "message" in update:
                    asyncio.create_task(_handle_message(update["message"]))
        except Exception as e:
            print(f"[telegram] Polling loop error: {e}")
            await asyncio.sleep(5)


def stop_polling():
    global _running
    _running = False
    print("[telegram] Bot stopped.")
