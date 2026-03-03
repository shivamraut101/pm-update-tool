from datetime import datetime, timedelta
from backend.database import get_db
from backend.utils.date_helpers import today_str, today_start, today_end
from backend.utils.logger import get_logger

logger = get_logger(__name__)

# Cooldown periods (prevent spamming same reminder)
COOLDOWN_HOURS = {
    "no_update_today": 3,      # Re-alert every 3 hours if still no updates
    "blocker_unresolved": 24,  # Re-alert daily for unresolved blockers
    "action_item_due": 12,     # Re-alert every 12 hours for high-priority items
    "reference_db_sync": 48,   # Re-alert every 2 days for auto-created entities
}

# TTL (time-to-live) - auto-dismiss old reminders
TTL_HOURS = {
    "no_update_today": 24,      # Dismiss after 24 hours (next day starts fresh)
    "blocker_unresolved": 168,  # Dismiss after 7 days (assume resolved if no new updates)
    "action_item_due": 72,      # Dismiss after 3 days
    "reference_db_sync": 336,   # Dismiss after 14 days (2 weeks)
}


async def run_reminder_checks():
    """Run all reminder checks. Called by the scheduler."""
    await _cleanup_expired_reminders()
    await _check_no_updates_today()
    await _check_stale_blockers()
    await _check_pending_action_items()
    await _send_unsent_high_priority_alerts()


async def _cleanup_expired_reminders():
    """Auto-dismiss reminders that exceeded their TTL."""
    db = get_db()
    for reminder_type, ttl_hours in TTL_HOURS.items():
        cutoff = datetime.utcnow() - timedelta(hours=ttl_hours)
        result = await db.reminders.update_many(
            {
                "type": reminder_type,
                "created_at": {"$lt": cutoff},
                "is_dismissed": False,
            },
            {
                "$set": {
                    "is_dismissed": True,
                    "dismissed_at": datetime.utcnow(),
                    "dismissed_reason": "auto_expired",
                }
            }
        )
        if result.modified_count > 0:
            logger.info(f"Auto-dismissed {result.modified_count} expired '{reminder_type}' reminders")


async def _check_no_updates_today():
    """Create a reminder if no updates have been submitted today."""
    db = get_db()
    date = today_str()
    count = await db.updates.count_documents({"date": date})

    # If updates exist, auto-dismiss any active "no_update_today" reminders
    if count > 0:
        result = await db.reminders.update_many(
            {
                "type": "no_update_today",
                "is_dismissed": False,
            },
            {
                "$set": {
                    "is_dismissed": True,
                    "dismissed_at": datetime.utcnow(),
                    "dismissed_reason": "condition_resolved",
                }
            }
        )
        if result.modified_count > 0:
            logger.info(f"Auto-dismissed {result.modified_count} 'no_update_today' reminders (updates submitted)")
        return

    # No updates - check if we need to create/re-alert
    cooldown_cutoff = datetime.utcnow() - timedelta(hours=COOLDOWN_HOURS["no_update_today"])
    existing = await db.reminders.find_one({
        "type": "no_update_today",
        "created_at": {"$gte": today_start()},
        "is_dismissed": False,
        "$or": [
            {"last_alerted_at": {"$exists": False}},  # Never alerted
            {"last_alerted_at": {"$lt": cooldown_cutoff}},  # Cooldown expired
        ]
    })

    if existing:
        # Update last_alerted_at and mark as unsent so it gets re-sent
        await db.reminders.update_one(
            {"_id": existing["_id"]},
            {
                "$set": {
                    "last_alerted_at": datetime.utcnow(),
                    "is_sent": False,
                }
            }
        )
        logger.info(f"Re-alerting 'no_update_today' after cooldown")
    else:
        # Create new reminder only if no recent one exists
        recent = await db.reminders.find_one({
            "type": "no_update_today",
            "created_at": {"$gte": cooldown_cutoff},
        })
        if not recent:
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
                "last_alerted_at": None,
                "created_at": datetime.utcnow(),
            })
            logger.info(f"Created 'no_update_today' reminder")


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

    # Build set of current blocker descriptions
    current_blocker_descs = {item["parsed"]["blockers"].get("description", "") for item in stale_blockers if item["parsed"]["blockers"].get("description")}

    # Auto-dismiss reminders for blockers that are no longer in the current list (assumed resolved)
    if current_blocker_descs:
        result = await db.reminders.update_many(
            {
                "type": "blocker_unresolved",
                "related_action_item": {"$nin": list(current_blocker_descs)},
                "is_dismissed": False,
            },
            {
                "$set": {
                    "is_dismissed": True,
                    "dismissed_at": datetime.utcnow(),
                    "dismissed_reason": "blocker_resolved",
                }
            }
        )
        if result.modified_count > 0:
            logger.info(f"Auto-dismissed {result.modified_count} 'blocker_unresolved' reminders (no longer in recent updates)")

    cooldown_cutoff = datetime.utcnow() - timedelta(hours=COOLDOWN_HOURS["blocker_unresolved"])

    for item in stale_blockers:
        blocker = item["parsed"]["blockers"]
        desc = blocker.get("description", "")
        needs_escalation = blocker.get("needs_escalation", False)

        # Check if we have a reminder that needs re-alerting
        existing = await db.reminders.find_one({
            "type": "blocker_unresolved",
            "related_action_item": desc,
            "is_dismissed": False,
            "$or": [
                {"last_alerted_at": {"$exists": False}},
                {"last_alerted_at": {"$lt": cooldown_cutoff}},
            ]
        })

        if existing:
            # Re-alert existing reminder after cooldown
            await db.reminders.update_one(
                {"_id": existing["_id"]},
                {
                    "$set": {
                        "last_alerted_at": datetime.utcnow(),
                        "is_sent": False,
                    }
                }
            )
            logger.info(f"Re-alerting blocker: {desc[:50]}...")
        else:
            # Check if a recent reminder exists (within cooldown)
            recent = await db.reminders.find_one({
                "type": "blocker_unresolved",
                "related_action_item": desc,
                "created_at": {"$gte": cooldown_cutoff},
            })
            if not recent:
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
                    "last_alerted_at": None,
                    "created_at": datetime.utcnow(),
                })
                logger.info(f"Created blocker reminder: {desc[:50]}...")


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

    # Build set of current pending action item descriptions
    current_action_descs = {item["parsed"]["action_items"].get("description", "") for item in items if item["parsed"]["action_items"].get("description")}

    # Auto-dismiss reminders for action items that are no longer pending (assumed completed or removed)
    if current_action_descs:
        result = await db.reminders.update_many(
            {
                "type": "action_item_due",
                "related_action_item": {"$nin": list(current_action_descs)},
                "is_dismissed": False,
            },
            {
                "$set": {
                    "is_dismissed": True,
                    "dismissed_at": datetime.utcnow(),
                    "dismissed_reason": "action_completed",
                }
            }
        )
        if result.modified_count > 0:
            logger.info(f"Auto-dismissed {result.modified_count} 'action_item_due' reminders (completed or removed)")

    cooldown_cutoff = datetime.utcnow() - timedelta(hours=COOLDOWN_HOURS["action_item_due"])

    for item in items:
        ai = item["parsed"]["action_items"]
        desc = ai.get("description", "")

        # Check if we have a reminder that needs re-alerting
        existing = await db.reminders.find_one({
            "type": "action_item_due",
            "related_action_item": desc,
            "is_dismissed": False,
            "$or": [
                {"last_alerted_at": {"$exists": False}},
                {"last_alerted_at": {"$lt": cooldown_cutoff}},
            ]
        })

        if existing:
            # Re-alert existing reminder after cooldown
            await db.reminders.update_one(
                {"_id": existing["_id"]},
                {
                    "$set": {
                        "last_alerted_at": datetime.utcnow(),
                        "is_sent": False,
                    }
                }
            )
            logger.info(f"Re-alerting action item: {desc[:50]}...")
        else:
            # Check if a recent reminder exists (within cooldown)
            recent = await db.reminders.find_one({
                "type": "action_item_due",
                "related_action_item": desc,
                "created_at": {"$gte": cooldown_cutoff},
            })
            if not recent:
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
                    "last_alerted_at": None,
                    "created_at": datetime.utcnow(),
                })
                logger.info(f"Created action item reminder: {desc[:50]}...")


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
            logger.error(f"Alert email send error: {e}")

        # Send via Telegram
        if settings.telegram_chat_id:
            try:
                from backend.services.telegram_bot import send_telegram_message
                emoji = _alert_emoji(reminder.get("type", ""))
                telegram_msg = f"{emoji} *Alert: {subject}*\n\n{msg}"
                await send_telegram_message(settings.telegram_chat_id, telegram_msg)
                sent_channels.append("telegram")
            except Exception as e:
                logger.error(f"Alert Telegram send error: {e}")

        if sent_channels:
            await db.reminders.update_one(
                {"_id": reminder["_id"]},
                {"$set": {
                    "is_sent": True,
                    "sent_via": ",".join(sent_channels),
                    "last_alerted_at": datetime.utcnow(),  # Track when alert was sent
                }},
            )


async def create_sync_reminder(entity_type: str, entity_name: str):
    """Create reminder to sync reference DB with new auto-created entity.

    Called by telegram_bot.py when auto-creating unknown entities.
    """
    db = get_db()
    reminder_key = f"{entity_type}:{entity_name}"

    existing = await db.reminders.find_one({
        "type": "reference_db_sync",
        "related_action_item": reminder_key,
        "is_dismissed": False,
    })

    if not existing:
        await db.reminders.insert_one({
            "type": "reference_db_sync",
            "message": (
                f"New {entity_type} '{entity_name}' was auto-created from an update. "
                f"Please add it to the reference database and run /sync to ensure consistency."
            ),
            "priority": "medium",
            "related_project_id": None,
            "related_action_item": reminder_key,
            "trigger_time": datetime.utcnow(),
            "is_dismissed": False,
            "is_sent": False,
            "sent_via": None,
            "last_alerted_at": None,
            "created_at": datetime.utcnow(),
        })
        logger.info(f"Created reference_db_sync reminder for {entity_type}: {entity_name}")


def _alert_emoji(alert_type: str) -> str:
    """Return an appropriate emoji for the alert type."""
    return {
        "no_update_today": "\u26a0\ufe0f",       # warning
        "blocker_unresolved": "\U0001f6a8",       # rotating light
        "action_item_due": "\u2757",              # exclamation mark
        "reference_db_sync": "\U0001f4cb",        # clipboard (sync/admin task)
    }.get(alert_type, "\U0001f514")               # bell
