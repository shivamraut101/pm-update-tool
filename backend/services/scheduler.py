from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from backend.config import settings
from backend.utils.date_helpers import today_str, week_boundaries

_scheduler = AsyncIOScheduler()


async def start_scheduler():
    """Start the APScheduler with all cron jobs."""
    tz = settings.timezone

    # Parse times
    daily_hour, daily_min = settings.daily_brief_time.split(":")
    weekly_day = settings.weekly_report_day[:3].lower()
    weekly_hour, weekly_min = settings.weekly_report_time.split(":")
    reminder_hour, reminder_min = settings.reminder_no_update_time.split(":")

    # Job 1: Daily brief generation + delivery
    _scheduler.add_job(
        _daily_brief_job,
        CronTrigger(
            hour=int(daily_hour),
            minute=int(daily_min),
            day_of_week="mon-fri",
            timezone=tz,
        ),
        id="daily_brief",
        replace_existing=True,
    )

    # Job 2: Weekly report generation + delivery
    _scheduler.add_job(
        _weekly_report_job,
        CronTrigger(
            day_of_week=weekly_day,
            hour=int(weekly_hour),
            minute=int(weekly_min),
            timezone=tz,
        ),
        id="weekly_report",
        replace_existing=True,
    )

    # Job 3: Reminder checks (hourly 10 AM - 6 PM, weekdays)
    _scheduler.add_job(
        _reminder_check_job,
        CronTrigger(
            hour="10-18",
            minute=0,
            day_of_week="mon-fri",
            timezone=tz,
        ),
        id="reminder_check",
        replace_existing=True,
    )

    # Job 4: No-update reminder
    _scheduler.add_job(
        _no_update_reminder_job,
        CronTrigger(
            hour=int(reminder_hour),
            minute=int(reminder_min),
            day_of_week="mon-fri",
            timezone=tz,
        ),
        id="no_update_reminder",
        replace_existing=True,
    )

    _scheduler.start()
    print(f"Scheduler started. Daily brief at {settings.daily_brief_time}, "
          f"Weekly report on {settings.weekly_report_day} at {settings.weekly_report_time}")


def stop_scheduler():
    """Stop the scheduler gracefully."""
    if _scheduler.running:
        _scheduler.shutdown(wait=False)


async def _daily_brief_job():
    """Generate and send daily brief."""
    from backend.services.report_generator import generate_daily_brief
    from backend.services.email_sender import send_daily_brief_email
    from backend.services.whatsapp_sender import send_report_whatsapp

    date = today_str()
    print(f"[Scheduler] Generating daily brief for {date}")

    report = await generate_daily_brief(date)
    if not report:
        print(f"[Scheduler] No updates for {date}, skipping daily brief")
        return

    # Send email
    emails = settings.get_management_emails_list()
    if emails:
        try:
            await send_daily_brief_email(report, emails)
            print(f"[Scheduler] Daily brief emailed to {emails}")
        except Exception as e:
            print(f"[Scheduler] Email send error: {e}")

    # Send WhatsApp
    numbers = settings.get_management_whatsapp_list()
    if numbers:
        try:
            await send_report_whatsapp(report, numbers)
            print(f"[Scheduler] Daily brief sent via WhatsApp to {numbers}")
        except Exception as e:
            print(f"[Scheduler] WhatsApp send error: {e}")


async def _weekly_report_job():
    """Generate and send weekly report."""
    from backend.services.report_generator import generate_weekly_report
    from backend.services.email_sender import send_weekly_report_email
    from backend.services.whatsapp_sender import send_report_whatsapp

    _, week_end = week_boundaries()
    print(f"[Scheduler] Generating weekly report ending {week_end}")

    report = await generate_weekly_report(week_end)
    if not report:
        print("[Scheduler] No daily reports found for weekly summary")
        return

    emails = settings.get_management_emails_list()
    if emails:
        try:
            await send_weekly_report_email(report, emails)
            print(f"[Scheduler] Weekly report emailed to {emails}")
        except Exception as e:
            print(f"[Scheduler] Email send error: {e}")

    numbers = settings.get_management_whatsapp_list()
    if numbers:
        try:
            await send_report_whatsapp(report, numbers)
            print(f"[Scheduler] Weekly report sent via WhatsApp")
        except Exception as e:
            print(f"[Scheduler] WhatsApp send error: {e}")


async def _reminder_check_job():
    """Run all reminder checks."""
    from backend.services.reminder_engine import run_reminder_checks
    print("[Scheduler] Running reminder checks")
    await run_reminder_checks()


async def _no_update_reminder_job():
    """Check if user has submitted updates today, remind if not."""
    from backend.services.reminder_engine import run_reminder_checks
    from backend.services.whatsapp_sender import send_reminder_whatsapp
    from backend.database import get_db

    db = get_db()
    date = today_str()
    count = await db.updates.count_documents({"date": date})

    if count == 0:
        print(f"[Scheduler] No updates today ({date}), sending reminder")
        await run_reminder_checks()
        try:
            await send_reminder_whatsapp(
                "You haven't submitted any project updates today. "
                "The daily brief goes out soon!"
            )
        except Exception as e:
            print(f"[Scheduler] Reminder WhatsApp error: {e}")
