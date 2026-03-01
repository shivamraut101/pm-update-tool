from datetime import datetime, timedelta
import pytz
from backend.config import settings


def get_timezone():
    return pytz.timezone(settings.timezone)


def now_local():
    tz = get_timezone()
    return datetime.now(tz)


def today_str():
    return now_local().strftime("%Y-%m-%d")


def today_start():
    tz = get_timezone()
    local_now = datetime.now(tz)
    return local_now.replace(hour=0, minute=0, second=0, microsecond=0)


def today_end():
    tz = get_timezone()
    local_now = datetime.now(tz)
    return local_now.replace(hour=23, minute=59, second=59, microsecond=999999)


def week_boundaries(reference_date=None):
    """Return (monday_date_str, friday_date_str) for the week containing reference_date."""
    if reference_date is None:
        reference_date = now_local().date()
    weekday = reference_date.weekday()  # Monday=0, Sunday=6
    monday = reference_date - timedelta(days=weekday)
    friday = monday + timedelta(days=4)
    return monday.strftime("%Y-%m-%d"), friday.strftime("%Y-%m-%d")


def format_date_display(date_str: str) -> str:
    """Convert 2026-03-01 to Saturday, March 1, 2026."""
    from dateutil.parser import parse
    dt = parse(date_str)
    return dt.strftime("%A, %B %d, %Y")
