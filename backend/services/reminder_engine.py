from datetime import datetime, timedelta
from backend.database import get_db
from backend.utils.date_helpers import today_str, today_start, today_end


async def run_reminder_checks():
    """Run all reminder checks. Called by the scheduler."""
    await _check_no_updates_today()
    await _check_stale_blockers()
    await _check_pending_action_items()
    await _send_unsent_high_priority_alerts()


async def _check_no_updates_today():
    """Create a reminder if no updates have been submitted today."""
    db = get_db()
    date = today_str()
    count = await db.updates.count_documents({"date": date})

    if count == 0:
        # Check if we already created this reminder today
        existing = await db.reminders.find_one({
            "type": "no_update_today",
            "created_at": {"$gte": today_start()},
            "is_dismissed": False,
        })
        if not existing:
            await db.reminders.insert_one({
                "type": "no_update_today",
                "message": (
                    "You haven't submitted any updates today. "
                    "The daily brief is scheduled to go out soon."
                ),
                "priority": "high",
                "related_project_id": None,
                "related_action_item": None,
                "trigger_time": datetime.utcnow(),
                "is_dismissed": False,
                "is_sent": False,
                "sent_via": None,
                "created_at": datetime.utcnow(),
            })


async def _check_stale_blockers():
    """Create reminders for blockers that have been open for more than 2 days."""
    db = get_db()
    two_days_ago = (datetime.utcnow() - timedelta(days=2)).strftime("%Y-%m-%d")

    # Find updates from 2+ days ago that have blockers
    pipeline = [
        {"$match": {"date": {"$lte": two_days_ago}}},
        {"$unwind": "$parsed.blockers"},
        {"$match": {"parsed.blockers.severity": {"$in": ["high", "medium"]}}},
        {"$sort": {"date": -1}},
        {"$limit": 10},
    ]
    stale_blockers = await db.updates.aggregate(pipeline).to_list(None)

    for item in stale_blockers:
        blocker = item["parsed"]["blockers"]
        desc = blocker.get("description", "")
        needs_escalation = blocker.get("needs_escalation", False)
        # Check if we already have a reminder for this blocker
        existing = await db.reminders.find_one({
            "type": "blocker_unresolved",
            "related_action_item": desc,
            "is_dismissed": False,
        })
        if not existing:
            priority = "high" if needs_escalation else blocker.get("severity", "medium")
            await db.reminders.insert_one({
                "type": "blocker_unresolved",
                "message": (
                    f"Blocker still open from {item['date']}: {desc} "
                    f"(Project: {blocker.get('project_name', 'N/A')}, "
                    f"Blocking: {blocker.get('blocking_who', 'N/A')})"
                    f"{' - NEEDS ESCALATION' if needs_escalation else ''}"
                ),
                "priority": priority,
                "related_project_id": blocker.get("project_id"),
                "related_action_item": desc,
                "trigger_time": datetime.utcnow(),
                "is_dismissed": False,
                "is_sent": False,
                "sent_via": None,
                "created_at": datetime.utcnow(),
            })


async def _check_pending_action_items():
    """Create reminders for uncompleted action items with high priority."""
    db = get_db()
    date = today_str()

    # Find today's action items that are high priority
    pipeline = [
        {"$match": {"date": date}},
        {"$unwind": "$parsed.action_items"},
        {"$match": {
            "parsed.action_items.priority": "high",
            "parsed.action_items.is_completed": False,
        }},
    ]
    items = await db.updates.aggregate(pipeline).to_list(None)

    for item in items:
        ai = item["parsed"]["action_items"]
        desc = ai.get("description", "")
        existing = await db.reminders.find_one({
            "type": "action_item_due",
            "related_action_item": desc,
            "is_dismissed": False,
        })
        if not existing:
            await db.reminders.insert_one({
                "type": "action_item_due",
                "message": f"Action item pending: {desc} (Assigned: {ai.get('assigned_to', 'self')})",
                "priority": "high",
                "related_project_id": None,
                "related_action_item": desc,
                "trigger_time": datetime.utcnow(),
                "is_dismissed": False,
                "is_sent": False,
                "sent_via": None,
                "created_at": datetime.utcnow(),
            })


async def _send_unsent_high_priority_alerts():
    """Send high-priority alerts via both email and Telegram."""
    from backend.services.email_sender import send_alert_email
    from backend.config import settings

    db = get_db()
    unsent = await db.reminders.find({
        "priority": "high",
        "is_sent": False,
        "is_dismissed": False,
    }).to_list(None)

    for reminder in unsent:
        sent_channels = []
        msg = reminder.get("message", "")
        subject = reminder.get("type", "Reminder").replace("_", " ").title()

        # Send via email
        try:
            await send_alert_email(subject=subject, message=msg)
            sent_channels.append("email")
        except Exception as e:
            print(f"Alert email send error: {e}")

        # Send via Telegram
        if settings.telegram_chat_id:
            try:
                from backend.services.telegram_bot import send_telegram_message
                emoji = _alert_emoji(reminder.get("type", ""))
                telegram_msg = f"{emoji} *Alert: {subject}*\n\n{msg}"
                await send_telegram_message(settings.telegram_chat_id, telegram_msg)
                sent_channels.append("telegram")
            except Exception as e:
                print(f"Alert Telegram send error: {e}")

        if sent_channels:
            await db.reminders.update_one(
                {"_id": reminder["_id"]},
                {"$set": {
                    "is_sent": True,
                    "sent_via": ",".join(sent_channels),
                }},
            )


def _alert_emoji(alert_type: str) -> str:
    """Return an appropriate emoji for the alert type."""
    return {
        "no_update_today": "\u26a0\ufe0f",       # warning
        "blocker_unresolved": "\U0001f6a8",       # rotating light
        "action_item_due": "\u2757",              # exclamation mark
    }.get(alert_type, "\U0001f514")               # bell
