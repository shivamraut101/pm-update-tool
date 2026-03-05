"""Telegram bot — supports both webhook mode (VPS/cloud) and polling mode (local)."""
import asyncio
import os
import re
import tempfile
import time
import traceback
from datetime import datetime
from collections import deque

import httpx

from backend.config import settings
from backend.database import get_db
from backend.services.ai_parser import parse_update
from backend.services.screenshot_processor import process_screenshots
from backend.utils.date_helpers import today_str
from backend.utils.logger import get_logger

logger = get_logger(__name__)

# Telegram Bot API
_bot_token = ""
_base_url = ""
_authorized_chat_id = ""
_running = False
_offset = 0
_webhook_mode = False

# Persistent HTTP client (avoids DNS re-resolution on every call)
_http_client: httpx.AsyncClient | None = None

# Deduplication: Track recently processed update IDs (keep last 100)
_processed_updates = deque(maxlen=100)

# Command locks: Prevent concurrent execution of expensive commands
_report_lock = asyncio.Lock()
_weekly_lock = asyncio.Lock()
_sync_lock = asyncio.Lock()
_undo_lock = asyncio.Lock()
_update_processing_lock = asyncio.Lock()


async def _get_client() -> httpx.AsyncClient:
    """Get or create a persistent HTTP client with connection pooling."""
    global _http_client
    if _http_client is None or _http_client.is_closed:
        _http_client = httpx.AsyncClient(
            timeout=httpx.Timeout(connect=10.0, read=45.0, write=10.0, pool=10.0),
            limits=httpx.Limits(max_connections=10, max_keepalive_connections=5),
        )
        logger.info("HTTP client created (persistent, connection-pooled)")
    return _http_client


async def _close_client():
    """Close the persistent HTTP client."""
    global _http_client
    if _http_client and not _http_client.is_closed:
        await _http_client.aclose()
        _http_client = None
        logger.info("HTTP client closed")


def configure_telegram(bot_token: str, authorized_chat_id: str = ""):
    global _bot_token, _base_url, _authorized_chat_id
    _bot_token = bot_token
    _base_url = f"https://api.telegram.org/bot{bot_token}"
    _authorized_chat_id = authorized_chat_id
    logger.info(f"Telegram configured | base_url=https://api.telegram.org/bot***{bot_token[-6:]} | authorized_chat={authorized_chat_id}")


def _safe_md(text: str) -> str:
    """Escape Telegram Markdown V1 special characters in user-generated text."""
    for ch in ("\\", "_", "*", "`", "["):
        text = text.replace(ch, f"\\{ch}")
    return text


async def send_telegram_message(chat_id: str, text: str):
    """Send a message to a Telegram chat. Falls back to plain text if Markdown fails."""
    if not _bot_token:
        logger.warning("send_telegram_message called but bot token not configured")
        return
    # Telegram message limit is 4096 chars
    if len(text) > 4000:
        text = text[:4000] + "\n..."
    t_start = time.time()
    client = await _get_client()
    try:
        # Try with Markdown first
        resp = await client.post(
            f"{_base_url}/sendMessage",
            json={"chat_id": chat_id, "text": text, "parse_mode": "Markdown"},
            timeout=30.0,
        )
        if resp.status_code == 200 and resp.json().get("ok"):
            logger.info(f"MSG SENT → chat={chat_id} | {len(text)} chars | {(time.time()-t_start)*1000:.0f}ms")
            return
        # Markdown failed — retry as plain text
        logger.warning(f"Markdown send failed (status={resp.status_code}, body={resp.text[:200]}), retrying as plain text")
        resp = await client.post(
            f"{_base_url}/sendMessage",
            json={"chat_id": chat_id, "text": text},
            timeout=30.0,
        )
        if resp.status_code == 200 and resp.json().get("ok"):
            logger.info(f"MSG SENT (plain) → chat={chat_id} | {len(text)} chars | {(time.time()-t_start)*1000:.0f}ms")
        else:
            logger.error(f"MSG SEND FAILED → chat={chat_id} | status={resp.status_code} | body={resp.text[:300]}")
    except Exception as e:
        logger.error(f"MSG SEND ERROR → chat={chat_id} | {type(e).__name__}: {e}\n{traceback.format_exc()}")


# ---------------------------------------------------------------------------
# Webhook Mode (for VPS / cloud deployment)
# ---------------------------------------------------------------------------

async def setup_webhook(app_url: str):
    """Register webhook with Telegram. Call on startup when deploying to VPS/cloud."""
    global _webhook_mode
    if not _bot_token:
        logger.warning("Bot token not configured — webhook not set")
        return False

    webhook_url = f"{app_url}/api/telegram/webhook"
    logger.info(f"Setting up webhook → {webhook_url}")
    try:
        client = await _get_client()
        # Delete any existing webhook first
        await client.post(f"{_base_url}/deleteWebhook", timeout=10.0)
        # Set new webhook
        resp = await client.post(
            f"{_base_url}/setWebhook",
            json={"url": webhook_url, "allowed_updates": ["message"]},
            timeout=10.0,
        )
        data = resp.json()
        if data.get("ok"):
            _webhook_mode = True
            logger.info(f"✅ Webhook registered: {webhook_url}")
            await _register_commands()
            return True
        else:
            logger.error(f"Webhook setup failed: {data}")
            return False
    except Exception as e:
        logger.error(f"Webhook setup error: {type(e).__name__}: {e}\n{traceback.format_exc()}")
        return False


async def remove_webhook():
    """Remove webhook (used when switching to polling mode)."""
    global _webhook_mode
    if not _bot_token:
        return
    try:
        client = await _get_client()
        await client.post(f"{_base_url}/deleteWebhook", timeout=10.0)
        _webhook_mode = False
        logger.info("Webhook removed")
    except Exception as e:
        logger.error(f"Webhook removal error: {type(e).__name__}: {e}")


async def handle_webhook_update(update: dict):
    """Process an incoming webhook update from Telegram. Called by FastAPI route."""
    update_id = update.get("update_id")
    logger.info(f"WEBHOOK RECV | update_id={update_id} | keys={list(update.keys())}")

    # Deduplication: Skip if we've already processed this update
    if update_id and update_id in _processed_updates:
        logger.debug(f"Skipping duplicate update_id: {update_id}")
        return

    if update_id:
        _processed_updates.append(update_id)

    if "message" in update:
        msg = update["message"]
        chat_id = msg.get("chat", {}).get("id", "?")
        text = msg.get("text", msg.get("caption", ""))[:80]
        logger.info(f"WEBHOOK MSG | chat={chat_id} | text={text}")
        await _handle_message(msg)
    else:
        logger.info(f"WEBHOOK SKIP | update_id={update_id} | no 'message' key (keys: {list(update.keys())})")


# ---------------------------------------------------------------------------
# Polling Mode (for local development)
# ---------------------------------------------------------------------------

async def start_polling():
    """Start long-polling loop for Telegram updates."""
    global _running, _offset
    if not _bot_token:
        logger.warning("Bot token not configured — Telegram bot disabled.")
        return

    # Remove any existing webhook so polling works
    await remove_webhook()

    _running = True
    logger.info("POLLING START | Beginning long-poll loop...")

    # Verify bot identity
    try:
        client = await _get_client()
        resp = await client.get(f"{_base_url}/getMe", timeout=10.0)
        data = resp.json()
        if data.get("ok"):
            bot_info = data["result"]
            bot_name = bot_info.get("username", "unknown")
            logger.info(f"POLLING OK | Bot: @{bot_name} (id={bot_info.get('id')}) | Polling active")
        else:
            logger.error(f"POLLING WARN | getMe failed: {data}")
    except Exception as e:
        logger.error(f"POLLING WARN | Could not verify bot identity: {type(e).__name__}: {e}")

    await _register_commands()
    logger.info(f"POLLING READY | Authorized chat={_authorized_chat_id} | Waiting for messages...")

    consecutive_errors = 0
    while _running:
        try:
            updates = await _get_updates(offset=_offset, timeout=30)
            if updates:
                logger.info(f"POLL RECV | {len(updates)} update(s) received")
            consecutive_errors = 0  # Reset on success
            for update in updates:
                _offset = update["update_id"] + 1

                # Deduplication: Skip if already processed (extra safety layer)
                if update["update_id"] in _processed_updates:
                    logger.debug(f"POLL SKIP | Duplicate update_id={update['update_id']}")
                    continue
                _processed_updates.append(update["update_id"])

                if "message" in update:
                    msg = update["message"]
                    text = msg.get("text", msg.get("caption", ""))[:80]
                    logger.info(f"POLL MSG | update_id={update['update_id']} | chat={msg['chat']['id']} | text={text}")
                    asyncio.create_task(_handle_message(msg))
        except Exception as e:
            consecutive_errors += 1
            # Exponential backoff: 5s, 10s, 20s, 30s max
            wait = min(5 * (2 ** (consecutive_errors - 1)), 30)
            logger.error(
                f"POLL ERROR | {type(e).__name__}: {e} | "
                f"consecutive_errors={consecutive_errors} | retry_in={wait}s"
            )
            if consecutive_errors >= 3:
                logger.error(f"POLL ERROR | Full traceback:\n{traceback.format_exc()}")
                # Reset the HTTP client on persistent errors (force new DNS resolution)
                logger.info("POLL RECOVER | Resetting HTTP client...")
                await _close_client()
            await asyncio.sleep(wait)


def stop_polling():
    global _running
    _running = False
    logger.info("POLLING STOP | Bot polling stopped")


async def cleanup():
    """Cleanup resources (call on shutdown)."""
    stop_polling()
    await _close_client()
    logger.info("Bot cleanup complete")


async def _get_updates(offset: int = 0, timeout: int = 30):
    """Fetch updates from Telegram using long-polling."""
    client = await _get_client()
    resp = await client.get(
        f"{_base_url}/getUpdates",
        params={"offset": offset, "timeout": timeout},
        timeout=timeout + 10,
    )
    if resp.status_code == 200:
        data = resp.json()
        if data.get("ok"):
            return data.get("result", [])
        logger.warning(f"POLL API | getUpdates not ok: {data}")
    else:
        logger.warning(f"POLL API | getUpdates status={resp.status_code}: {resp.text[:200]}")
    return []


# ---------------------------------------------------------------------------
# Command registration
# ---------------------------------------------------------------------------

async def _register_commands():
    commands = [
        {"command": "start", "description": "Welcome + setup info"},
        {"command": "status", "description": "Quick counts for today"},
        {"command": "today", "description": "Detailed parsed updates today"},
        {"command": "pending", "description": "Team members with no updates"},
        {"command": "projects", "description": "List all active projects"},
        {"command": "team", "description": "List all team members"},
        {"command": "reminders", "description": "Show active reminders"},
        {"command": "sync", "description": "Re-sync projects & team from reference DB"},
        {"command": "report", "description": "Generate & send daily brief"},
        {"command": "week", "description": "Generate & send weekly report"},
        {"command": "undo", "description": "Delete last submitted update"},
        {"command": "help", "description": "Show all commands"},
    ]
    try:
        client = await _get_client()
        resp = await client.post(
            f"{_base_url}/setMyCommands",
            json={"commands": commands},
            timeout=10.0,
        )
        data = resp.json()
        if data.get("ok"):
            logger.info(f"Bot commands registered ({len(commands)} commands)")
        else:
            logger.warning(f"Bot commands registration failed: {data}")
    except Exception as e:
        logger.error(f"Bot commands registration error: {type(e).__name__}: {e}")


# ---------------------------------------------------------------------------
# Photo download + temp file processing
# ---------------------------------------------------------------------------

async def _download_photo(file_id: str) -> bytes | None:
    logger.info(f"PHOTO DOWNLOAD | file_id={file_id}")
    try:
        client = await _get_client()
        resp = await client.get(
            f"{_base_url}/getFile",
            params={"file_id": file_id},
            timeout=15.0,
        )
        data = resp.json()
        if not data.get("ok"):
            logger.error(f"PHOTO DOWNLOAD FAILED | getFile response: {data}")
            return None
        file_path = data["result"]["file_path"]
        file_size = data["result"].get("file_size", "?")
        logger.info(f"PHOTO DOWNLOAD | file_path={file_path} | size={file_size}")
        resp = await client.get(
            f"https://api.telegram.org/file/bot{_bot_token}/{file_path}",
            timeout=30.0,
        )
        if resp.status_code == 200:
            logger.info(f"PHOTO DOWNLOAD OK | {len(resp.content)} bytes received")
            return resp.content
        logger.error(f"PHOTO DOWNLOAD FAILED | status={resp.status_code}")
    except Exception as e:
        logger.error(f"PHOTO DOWNLOAD ERROR | {type(e).__name__}: {e}\n{traceback.format_exc()}")
    return None


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
        logger.error(f"Screenshot extraction error: {e}")
        return ""
    finally:
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except Exception:
                pass


# ---------------------------------------------------------------------------
# Message handler
# ---------------------------------------------------------------------------

async def _handle_message(message: dict):
    chat_id = str(message["chat"]["id"])
    from_user = message.get("from", {})
    username = from_user.get("username", "?")
    first_name = from_user.get("first_name", "?")

    if _authorized_chat_id and chat_id != _authorized_chat_id:
        logger.warning(f"UNAUTHORIZED | chat={chat_id} user=@{username} ({first_name}) | rejected")
        await send_telegram_message(
            chat_id,
            "🔒 *Unauthorized Access*\n\n"
            f"Your Chat ID: `{chat_id}`\n\n"
            "Ask your admin to authorize this chat ID.",
        )
        return

    text = message.get("text", "") or message.get("caption", "") or ""
    has_photo = "photo" in message
    lower_text = text.strip().lower()

    # Log incoming message with details
    msg_type = "photo" if has_photo else ("command" if lower_text.startswith("/") else "text")
    logger.info(f"MSG RECV | chat={chat_id} | user=@{username} | type={msg_type} | text={text[:120]}")

    # Command dispatch with logging
    t_cmd = time.time()
    if lower_text == "/start":
        await _cmd_start(chat_id)
        logger.info(f"CMD DONE | /start | {(time.time()-t_cmd)*1000:.0f}ms")
        return
    if lower_text in ("/help", "help"):
        await _cmd_help(chat_id)
        logger.info(f"CMD DONE | /help | {(time.time()-t_cmd)*1000:.0f}ms")
        return
    if lower_text in ("/status", "status"):
        await _cmd_status(chat_id)
        logger.info(f"CMD DONE | /status | {(time.time()-t_cmd)*1000:.0f}ms")
        return
    if lower_text == "/today":
        await _cmd_today(chat_id)
        logger.info(f"CMD DONE | /today | {(time.time()-t_cmd)*1000:.0f}ms")
        return
    if lower_text == "/pending":
        await _cmd_pending(chat_id)
        logger.info(f"CMD DONE | /pending | {(time.time()-t_cmd)*1000:.0f}ms")
        return
    if lower_text == "/projects":
        await _cmd_projects(chat_id)
        logger.info(f"CMD DONE | /projects | {(time.time()-t_cmd)*1000:.0f}ms")
        return
    if lower_text == "/team":
        await _cmd_team(chat_id)
        logger.info(f"CMD DONE | /team | {(time.time()-t_cmd)*1000:.0f}ms")
        return
    if lower_text == "/reminders":
        await _cmd_reminders(chat_id)
        logger.info(f"CMD DONE | /reminders | {(time.time()-t_cmd)*1000:.0f}ms")
        return
    if lower_text == "/sync":
        await _cmd_sync(chat_id)
        logger.info(f"CMD DONE | /sync | {(time.time()-t_cmd)*1000:.0f}ms")
        return
    if lower_text == "/report":
        await _cmd_report(chat_id)
        logger.info(f"CMD DONE | /report | {(time.time()-t_cmd)*1000:.0f}ms")
        return
    if lower_text == "/week":
        await _cmd_week(chat_id)
        logger.info(f"CMD DONE | /week | {(time.time()-t_cmd)*1000:.0f}ms")
        return
    if lower_text == "/undo":
        await _cmd_undo(chat_id)
        logger.info(f"CMD DONE | /undo | {(time.time()-t_cmd)*1000:.0f}ms")
        return

    logger.info(f"UPDATE PROC | Treating as project update text...")
    await _process_update(chat_id, message, text)
    logger.info(f"UPDATE DONE | {(time.time()-t_cmd)*1000:.0f}ms")


# ---------------------------------------------------------------------------
# Update processing (with temp screenshot handling — no disk persistence)
# ---------------------------------------------------------------------------

async def _auto_create_unknown_entities(parsed: dict, db, projects: list, team_members: list) -> list:
    """Auto-create unknown projects, team members, and clients found in parsed update.

    Returns list of created entity descriptions for user feedback.
    """
    from backend.services.reminder_engine import create_sync_reminder

    created = []
    projects_by_id = {str(p["_id"]): p for p in projects}
    members_by_id = {str(t["_id"]): t for t in team_members}

    # --- Auto-create unknown PROJECTS ---
    for tu in parsed.get("team_updates", []):
        if not tu.get("project_id") and tu.get("project_name"):
            proj_name = tu["project_name"].strip()

            # Double-check it doesn't exist (case-insensitive)
            existing = await db.projects.find_one(
                {"name": {"$regex": f"^{re.escape(proj_name)}$", "$options": "i"}}
            )
            if not existing:
                # Auto-create project
                new_proj = {
                    "name": proj_name,
                    "code": proj_name[:3].upper() if len(proj_name) >= 3 else proj_name.upper(),
                    "client_name": "",
                    "description": f"Auto-created from update on {today_str()}",
                    "status": "active",
                    "team_member_ids": [],
                    "auto_created": True,
                    "needs_reference_sync": True,
                    "created_at": datetime.utcnow(),
                    "updated_at": datetime.utcnow(),
                }
                result = await db.projects.insert_one(new_proj)
                new_proj_id = str(result.inserted_id)

                # Update parsed data with new ID
                tu["project_id"] = new_proj_id

                # Add to in-memory list for subsequent updates from same projects
                projects_by_id[new_proj_id] = new_proj

                # Create reminder
                await create_sync_reminder("project", proj_name)
                created.append(f"Project: {proj_name}")
                logger.info(f"Auto-created project: {proj_name}")

    # --- Auto-create unknown TEAM MEMBERS ---
    for tu in parsed.get("team_updates", []):
        if not tu.get("team_member_id") and tu.get("team_member_name"):
            member_name = tu["team_member_name"].strip()

            # Double-check doesn't exist (case-insensitive)
            existing = await db.team_members.find_one(
                {"name": {"$regex": f"^{re.escape(member_name)}$", "$options": "i"}}
            )
            if not existing:
                # Auto-create team member
                new_member = {
                    "name": member_name,
                    "nickname": "",
                    "aliases": [],
                    "role": "Developer",  # Default role
                    "email": "",
                    "project_ids": [],
                    "is_active": True,
                    "auto_created": True,
                    "needs_reference_sync": True,
                    "created_at": datetime.utcnow(),
                }
                result = await db.team_members.insert_one(new_member)
                new_member_id = str(result.inserted_id)

                # Update parsed data with new ID
                tu["team_member_id"] = new_member_id

                # Add to in-memory list
                members_by_id[new_member_id] = new_member

                # Create reminder
                await create_sync_reminder("team_member", member_name)
                created.append(f"Team Member: {member_name}")
                logger.info(f"Auto-created team member: {member_name}")

    # --- Auto-create unknown CLIENTS and link to projects ---
    for cu in parsed.get("client_updates", []):
        client_name = cu.get("client_name", "").strip()
        proj_name = cu.get("project_name", "").strip()
        if not client_name:
            continue

        # Check if client exists
        existing_client = await db.clients.find_one(
            {"name": {"$regex": f"^{re.escape(client_name)}$", "$options": "i"}}
        )

        if not existing_client:
            # Auto-create client
            new_client = {
                "name": client_name,
                "project_ids": [],
                "contact_email": "",
                "auto_created": True,
                "created_at": datetime.utcnow(),
            }
            result = await db.clients.insert_one(new_client)
            client_id = str(result.inserted_id)

            # Create reminder
            await create_sync_reminder("client", client_name)
            created.append(f"Client: {client_name}")
            logger.info(f"Auto-created client: {client_name}")
        else:
            client_id = str(existing_client["_id"])

        # Link client to project if project_id exists
        if cu.get("project_id"):
            # Update project with client_id
            await db.projects.update_one(
                {"_id": cu["project_id"]},
                {"$set": {"client_id": client_id, "client_name": client_name}}
            )
            # Update client with project_id
            await db.clients.update_one(
                {"_id": client_id},
                {"$addToSet": {"project_ids": cu["project_id"]}}
            )

    return created


async def _process_update(chat_id: str, message: dict, text: str):
    # Prevent concurrent update processing from same user
    if _update_processing_lock.locked():
        logger.info("UPDATE LOCK | Processing lock busy, waiting...")
    async with _update_processing_lock:
        t_start = time.time()
        logger.info(f"UPDATE START | chat={chat_id} | text={text[:120]}")
        await send_telegram_message(chat_id, "Processing your update...")

        screenshot_text = ""
        if "photo" in message:
            t_photo = time.time()
            photo = message["photo"][-1]
            photo_data = await _download_photo(photo["file_id"])
            if photo_data:
                screenshot_text = await _extract_and_cleanup_screenshot(photo_data)
            logger.info(f"Screenshot processing took {time.time() - t_photo:.1f}s (extracted={len(screenshot_text)} chars)")

        combined_text = text
        if screenshot_text:
            combined_text += f"\n\n[Screenshot content]: {screenshot_text}"

        if not combined_text.strip():
            await send_telegram_message(chat_id, "No text or image content to process.")
            return

        db = get_db()
        date = today_str()
        t_db = time.time()
        projects = await db.projects.find({"status": "active"}).to_list(None)
        team_members = await db.team_members.find({"is_active": True}).to_list(None)
        logger.info(f"DB context fetch took {time.time() - t_db:.1f}s ({len(projects)} projects, {len(team_members)} members)")

        try:
            t_ai = time.time()
            parsed, confidence = await parse_update(combined_text, projects, team_members)
            team_updates = parsed.get("team_updates", [])
            action_items = parsed.get("action_items", [])
            blockers = parsed.get("blockers", [])
            logger.info(
                f"AI parse took {time.time() - t_ai:.1f}s — "
                f"confidence={confidence:.2f}, "
                f"team_updates={len(team_updates)}, "
                f"action_items={len(action_items)}, "
                f"blockers={len(blockers)}"
            )
        except Exception as e:
            logger.error(f"AI PARSE ERROR | after {time.time() - t_start:.1f}s | {type(e).__name__}: {e}\n{traceback.format_exc()}")
            await send_telegram_message(
                chat_id,
                f"❌ *AI Parsing Error*\n\n{_safe_md(str(e)[:200])}",
            )
            return

        # Auto-create unknown entities and update parsed data with new IDs
        auto_created = await _auto_create_unknown_entities(parsed, db, projects, team_members)
        if auto_created:
            logger.info(f"Auto-created entities: {', '.join(auto_created)}")

        update_doc = {
            "raw_text": text,
            "source": "telegram",
            "has_screenshot": bool(screenshot_text),
            "screenshot_paths": [],
            "screenshot_extracted_text": screenshot_text,
            "parsed": parsed,
            "ai_confidence": confidence,
            "created_at": datetime.utcnow(),
            "date": date,
        }
        await db.updates.insert_one(update_doc)

        ack_parts = ["✅ *Update Saved!*"]
        if team_updates:
            names = set(t["team_member_name"] for t in team_updates)
            projects_mentioned = set(t["project_name"] for t in team_updates)
            ack_parts.append(f"\n*Team:* {', '.join(names)}")
            ack_parts.append(f"*Projects:* {', '.join(projects_mentioned)}")
        if action_items:
            ack_parts.append(f"*{len(action_items)}* action item(s) noted")
        if blockers:
            ack_parts.append(f"🔴 *{len(blockers)}* blocker(s) flagged")

        # Notify about auto-created entities
        if auto_created:
            ack_parts.append(f"\n⚠️ *Auto-created:*\n" + "\n".join(f"  - {e}" for e in auto_created))
            ack_parts.append("\nAdd these to your reference DB and run /sync.")

        await send_telegram_message(chat_id, "\n".join(ack_parts))
        logger.info(f"Update processed in {time.time() - t_start:.1f}s total")


# ---------------------------------------------------------------------------
# Command handlers
# ---------------------------------------------------------------------------

async def _cmd_start(chat_id: str):
    logger.info(f"Command: /start from chat={chat_id}")
    await send_telegram_message(
        chat_id,
        "*Welcome to PM Update Tool!* 👋\n\n"
        "Send your daily updates naturally — I'll parse and track everything with AI.\n\n"
        "*Commands:*\n"
        "├ /status — Today's overview\n"
        "├ /today — Detailed parsed updates\n"
        "├ /pending — Who's missing updates\n"
        "├ /projects — Active projects\n"
        "├ /team — Team members\n"
        "├ /reminders — Active reminders\n"
        "├ /report — Generate daily brief\n"
        "├ /week — Generate weekly report\n"
        "├ /sync — Sync reference DB\n"
        "├ /undo — Delete last update\n"
        "└ /help — All commands\n\n"
        "*Example:*\n"
        "_Yash fixed the login bug on B2B Portal. Shobhit pushed API docs PR._\n\n"
        f"Your Chat ID: `{chat_id}`",
    )


async def _cmd_help(chat_id: str):
    logger.info(f"Command: /help from chat={chat_id}")
    await send_telegram_message(
        chat_id,
        "*PM Update Tool — Commands*\n\n"
        "*Input*\n"
        "  Send text updates or screenshots — I'll parse them.\n\n"
        "*Review*\n"
        "├ /status — Quick counts for today\n"
        "├ /today — Detailed view (who did what)\n"
        "├ /pending — Team members with no updates\n"
        "├ /projects — All active projects\n"
        "├ /team — All team members\n"
        "└ /reminders — Active reminders\n\n"
        "*Actions*\n"
        "├ /report — Generate & send daily brief\n"
        "├ /week — Generate & send weekly report\n"
        "├ /sync — Re-sync from reference DB\n"
        "└ /undo — Delete last submitted update",
    )


async def _cmd_status(chat_id: str):
    logger.info(f"Command: /status from chat={chat_id}")
    db = get_db()
    date = today_str()
    count = await db.updates.count_documents({"date": date})
    if count == 0:
        await send_telegram_message(
            chat_id,
            "*No updates yet today.*\n\n"
            "Send me an update to get started!",
        )
        return
    updates = await db.updates.find({"date": date}).to_list(None)
    total_team = sum(len(u.get("parsed", {}).get("team_updates", [])) for u in updates)
    total_actions = sum(len(u.get("parsed", {}).get("action_items", [])) for u in updates)
    total_blockers = sum(len(u.get("parsed", {}).get("blockers", [])) for u in updates)
    blocker_icon = "🔴" if total_blockers > 0 else "✅"
    await send_telegram_message(
        chat_id,
        f"*Today's Status — {date}*\n\n"
        f"  *{count}* update(s) submitted\n"
        f"  *{total_team}* team activities\n"
        f"  *{total_actions}* action item(s)\n"
        f"{blocker_icon} *{total_blockers}* blocker(s)",
    )


async def _cmd_today(chat_id: str):
    logger.info(f"Command: /today from chat={chat_id}")
    db = get_db()
    date = today_str()
    updates = await db.updates.find({"date": date}).to_list(None)

    if not updates:
        await send_telegram_message(
            chat_id,
            "*No updates yet today.*\n\n"
            "Send me an update to get started!",
        )
        return

    status_icons = {
        "completed": "✅",
        "in_progress": "🔄",
        "blocked": "🚫",
        "not_started": "⏳",
    }

    priority_icons = {
        "high": "🔴",
        "medium": "🟡",
        "low": "🟢",
    }

    lines = [f"*Today's Updates — {date}*"]
    from collections import defaultdict
    by_project = defaultdict(list)

    # Deduplicate team updates based on (member, project, summary, status)
    seen_updates = set()

    for u in updates:
        for tu in u.get("parsed", {}).get("team_updates", []):
            # Create unique key for deduplication
            key = (
                tu.get("team_member_name", ""),
                tu.get("project_name", "Unassigned"),
                tu.get("summary", ""),
                tu.get("status", "")
            )
            if key not in seen_updates:
                seen_updates.add(key)
                by_project[tu.get("project_name", "Unassigned")].append(tu)

    if by_project:
        for proj, tus in sorted(by_project.items()):
            lines.append(f"\n*{_safe_md(proj)}*")
            for tu in tus:
                name = _safe_md(tu.get("team_member_name", "?"))
                summary = _safe_md(tu.get("summary", ""))
                status = tu.get("status", "")
                icon = status_icons.get(status, "▪️")
                lines.append(f"  {icon} *{name}*: {summary}")

    # Deduplicate action items
    all_actions = []
    seen_actions = set()
    for u in updates:
        for ai in u.get("parsed", {}).get("action_items", []):
            # Create unique key: (description, assigned_to, priority)
            key = (ai.get("description", ""), ai.get("assigned_to", ""), ai.get("priority", ""))
            if key not in seen_actions:
                seen_actions.add(key)
                all_actions.append(ai)

    if all_actions:
        lines.append(f"\n*Action Items ({len(all_actions)})*")
        for ai in all_actions:
            desc = _safe_md(ai.get("description", ""))
            assigned = _safe_md(ai.get("assigned_to", "self"))
            icon = priority_icons.get(ai.get("priority", "medium"), "🟡")
            lines.append(f"  {icon} {desc} → _{assigned}_")

    # Deduplicate blockers
    all_blockers = []
    seen_blockers = set()
    for u in updates:
        for b in u.get("parsed", {}).get("blockers", []):
            # Create unique key: (project_name, description, severity)
            key = (b.get("project_name", ""), b.get("description", ""), b.get("severity", ""))
            if key not in seen_blockers:
                seen_blockers.add(key)
                all_blockers.append(b)

    if all_blockers:
        lines.append(f"\n*Blockers ({len(all_blockers)})*")
        for b in all_blockers:
            proj = _safe_md(b.get("project_name", ""))
            desc = _safe_md(b.get("description", ""))
            severity = b.get("severity", "medium")
            icon = priority_icons.get(severity, "🟡")
            lines.append(f"  {icon} *{proj}*: {desc}")

    await send_telegram_message(chat_id, "\n".join(lines))


async def _cmd_pending(chat_id: str):
    logger.info(f"Command: /pending from chat={chat_id}")
    db = get_db()
    date = today_str()
    all_members = await db.team_members.find({"is_active": True}).to_list(None)
    updates = await db.updates.find({"date": date}).to_list(None)

    mentioned_ids = set()
    mentioned_names = set()
    for u in updates:
        for tu in u.get("parsed", {}).get("team_updates", []):
            if tu.get("team_member_id"):
                mentioned_ids.add(tu["team_member_id"])
            mentioned_names.add(tu.get("team_member_name", "").lower())

    missing = []
    covered = []
    for m in all_members:
        if str(m["_id"]) in mentioned_ids or m["name"].lower() in mentioned_names:
            covered.append(m["name"])
        else:
            missing.append(m["name"])

    total = len(all_members)
    coverage_pct = int(len(covered) / total * 100) if total > 0 else 0

    lines = [
        f"*Team Coverage — {date}*",
        f"\n*{coverage_pct}%* covered ({len(covered)}/{total} members)",
    ]

    if covered:
        lines.append(f"\n✅ *Updated ({len(covered)})*")
        for name in sorted(covered):
            lines.append(f"  - {_safe_md(name)}")
    if missing:
        lines.append(f"\n⏳ *Pending ({len(missing)})*")
        for name in sorted(missing):
            lines.append(f"  - {_safe_md(name)}")
    else:
        lines.append(f"\n*All team members have reported today!*")

    await send_telegram_message(chat_id, "\n".join(lines))


async def _cmd_projects(chat_id: str):
    logger.info(f"Command: /projects from chat={chat_id}")
    db = get_db()
    projects = await db.projects.find({"status": "active"}).to_list(None)

    if not projects:
        await send_telegram_message(
            chat_id,
            "*No active projects found.*\n\n"
            "Add projects via the web dashboard or reference DB, then run /sync.",
        )
        return

    lines = [f"*Active Projects ({len(projects)})*"]
    for p in sorted(projects, key=lambda x: x.get("name", "")):
        name = _safe_md(p.get("name", "Unknown"))
        code = p.get("code", "")
        health = p.get("health", "unknown")
        members = len(p.get("team_member_ids", []))
        health_icon = {"on_track": "🟢", "at_risk": "🟡", "off_track": "🔴"}.get(health, "⚪")
        auto_tag = " _(auto)_" if p.get("auto_created") else ""
        lines.append(f"\n{health_icon} *{name}* `[{code}]`{auto_tag}")
        lines.append(f"    {members} member(s)")
        if p.get("client_name"):
            lines.append(f"    Client: {_safe_md(p['client_name'])}")
        if p.get("tech_stack"):
            lines.append(f"    Tech: {', '.join(p['tech_stack'])}")

    await send_telegram_message(chat_id, "\n".join(lines))


async def _cmd_team(chat_id: str):
    logger.info(f"Command: /team from chat={chat_id}")
    db = get_db()
    members = await db.team_members.find({"is_active": True}).to_list(None)

    if not members:
        await send_telegram_message(
            chat_id,
            "*No active team members found.*\n\n"
            "Add team members via the web dashboard or reference DB, then run /sync.",
        )
        return

    lines = [f"*Team Members ({len(members)})*"]
    for m in sorted(members, key=lambda x: x.get("name", "")):
        name = _safe_md(m.get("name", "Unknown"))
        role = m.get("role", "")
        project_count = len(m.get("project_ids", []))
        auto_tag = " _(auto)_" if m.get("auto_created") else ""
        role_str = f" — {role}" if role else ""
        lines.append(f"\n*{name}*{auto_tag}{role_str}")
        lines.append(f"    {project_count} project(s)")

    await send_telegram_message(chat_id, "\n".join(lines))


async def _cmd_reminders(chat_id: str):
    logger.info(f"Command: /reminders from chat={chat_id}")
    db = get_db()
    reminders = await db.reminders.find({"is_dismissed": False}).to_list(None)

    if not reminders:
        await send_telegram_message(chat_id, "*No active reminders.* All caught up!")
        return

    priority_icon = {"high": "🔴", "medium": "🟡", "low": "🟢"}
    lines = [f"*Active Reminders ({len(reminders)})*"]
    for r in reminders:
        icon = priority_icon.get(r.get("priority", "medium"), "⚪")
        rtype = r.get("type", "").replace("_", " ").title()
        msg = _safe_md(r.get("message", ""))
        lines.append(f"\n{icon} *{rtype}*")
        lines.append(f"    {msg}")

    await send_telegram_message(chat_id, "\n".join(lines))


async def _cmd_sync(chat_id: str):
    logger.info(f"Command: /sync from chat={chat_id}")
    # Prevent concurrent sync operations
    if _sync_lock.locked():
        logger.warning("Sync already running, rejecting request")
        await send_telegram_message(chat_id, "A sync operation is already running. Please wait...")
        return

    async with _sync_lock:
        await send_telegram_message(chat_id, "Syncing from reference database...")
        try:
            from backend.services.ref_sync import sync_from_reference_db
            await sync_from_reference_db()

            db = get_db()
            members = await db.team_members.count_documents({"is_active": True})
            projects = await db.projects.count_documents({"status": "active"})
            clients = await db.clients.count_documents({})

            await send_telegram_message(
                chat_id,
                f"✅ *Sync Complete*\n\n"
                f"  *{members}* team member(s)\n"
                f"  *{projects}* active project(s)\n"
                f"  *{clients}* client(s)",
            )
        except Exception as e:
            logger.error(f"SYNC ERROR | {type(e).__name__}: {e}\n{traceback.format_exc()}")
            await send_telegram_message(
                chat_id,
                f"❌ *Sync Failed*\n\n{_safe_md(str(e)[:200])}",
            )


async def _cmd_report(chat_id: str):
    logger.info(f"Command: /report from chat={chat_id}")
    # Prevent concurrent report generation
    if _report_lock.locked():
        logger.warning("Daily report already generating, rejecting request")
        await send_telegram_message(chat_id, "A daily brief is already being generated. Please wait...")
        return

    async with _report_lock:
        await send_telegram_message(chat_id, "Generating daily brief...")
        from backend.services.report_generator import generate_daily_brief
        from backend.services.email_sender import send_daily_brief_email

        try:
            report = await generate_daily_brief(today_str())
        except Exception as e:
            logger.error(f"REPORT ERROR | {type(e).__name__}: {e}\n{traceback.format_exc()}")
            await send_telegram_message(
                chat_id,
                f"❌ *Report Generation Failed*\n\n{_safe_md(str(e)[:200])}",
            )
            return

        if not report:
            await send_telegram_message(
                chat_id,
                "*No updates today* — nothing to generate.\n\n"
                "Send some updates first, then try again.",
            )
            return

        results = []
        emails = settings.get_management_emails_list()
        if emails:
            try:
                await send_daily_brief_email(report, emails)
                results.append(f"Email sent to {', '.join(emails)}")
            except Exception as e:
                results.append(f"Email failed: {str(e)[:100]}")

        # Send report to management via Telegram
        mgmt_chat_id = settings.management_telegram_chat_id
        if mgmt_chat_id:
            try:
                plain = report.get("content_plain") or report.get("content_markdown", "")
                await send_telegram_message(mgmt_chat_id, f"*Daily Brief — {today_str()}*\n\n{plain}")
                results.append(f"Telegram sent to management")
            except Exception as e:
                results.append(f"Telegram failed: {str(e)[:100]}")

        lines = [f"✅ *Daily Brief Generated*\n"]
        lines.extend(f"  - {r}" for r in results)
        if not results:
            lines.append("No delivery channels configured. Set up email or Telegram in settings.")
        await send_telegram_message(chat_id, "\n".join(lines))


async def _cmd_week(chat_id: str):
    logger.info(f"Command: /week from chat={chat_id}")
    # Prevent concurrent weekly report generation
    if _weekly_lock.locked():
        logger.warning("Weekly report already generating, rejecting request")
        await send_telegram_message(chat_id, "A weekly report is already being generated. Please wait...")
        return

    async with _weekly_lock:
        await send_telegram_message(chat_id, "Generating weekly report...")
        from backend.services.report_generator import generate_weekly_report
        from backend.services.email_sender import send_weekly_report_email
        from backend.utils.date_helpers import week_boundaries

        try:
            _, week_end = week_boundaries()
            report = await generate_weekly_report(week_end)
        except Exception as e:
            logger.error(f"WEEKLY REPORT ERROR | {type(e).__name__}: {e}\n{traceback.format_exc()}")
            await send_telegram_message(
                chat_id,
                f"❌ *Weekly Report Failed*\n\n{_safe_md(str(e)[:200])}",
            )
            return

        if not report:
            await send_telegram_message(
                chat_id,
                "*No daily reports this week* — nothing to synthesize.\n\n"
                "Generate daily briefs first, then try the weekly report.",
            )
            return

        results = []
        emails = settings.get_management_emails_list()
        if emails:
            try:
                await send_weekly_report_email(report, emails)
                results.append(f"Email sent to {', '.join(emails)}")
            except Exception as e:
                results.append(f"Email failed: {str(e)[:100]}")

        # Send report to management via Telegram
        mgmt_chat_id = settings.management_telegram_chat_id
        if mgmt_chat_id:
            try:
                plain = report.get("content_plain") or report.get("content_markdown", "")
                await send_telegram_message(mgmt_chat_id, f"*Weekly Report*\n\n{plain}")
                results.append(f"Telegram sent to management")
            except Exception as e:
                results.append(f"Telegram failed: {str(e)[:100]}")

        lines = [f"✅ *Weekly Report Generated*\n"]
        lines.extend(f"  - {r}" for r in results)
        if not results:
            lines.append("No delivery channels configured. Set up email or Telegram in settings.")
        await send_telegram_message(chat_id, "\n".join(lines))


async def _cmd_undo(chat_id: str):
    logger.info(f"Command: /undo from chat={chat_id}")
    # Prevent concurrent undo operations
    if _undo_lock.locked():
        logger.warning("Undo already running, rejecting request")
        await send_telegram_message(chat_id, "An undo operation is already running. Please wait...")
        return

    async with _undo_lock:
        db = get_db()
        date = today_str()
        last_update = await db.updates.find_one(
            {"date": date, "source": {"$in": ["telegram", "web"]}},
            sort=[("created_at", -1)],
        )
        if not last_update:
            await send_telegram_message(chat_id, "*Nothing to undo.* No updates submitted today.")
            return

        raw = last_update.get("raw_text", "")[:100]
        team_updates = last_update.get("parsed", {}).get("team_updates", [])
        preview = _safe_md(raw) if raw else f"{len(team_updates)} team update(s)"
        await db.updates.delete_one({"_id": last_update["_id"]})
        await send_telegram_message(
            chat_id,
            f"✅ *Update Deleted*\n\n"
            f"_{preview}_\n\n"
            f"Send /today to review remaining updates.",
        )
