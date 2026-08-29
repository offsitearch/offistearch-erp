"""Business timezone primitives (kernel k0).

The studio operates in ``Asia/Kolkata``. All currency money handling pairs with
these helpers; no raw ``datetime.now()`` outside this module.
"""

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

APP_TZ = ZoneInfo("Asia/Kolkata")


def utc_now() -> datetime:
    """Current UTC datetime (timezone-aware)."""
    return datetime.now(timezone.utc)


def now_local() -> datetime:
    """Current datetime in the studio's business timezone (Asia/Kolkata)."""
    return datetime.now(APP_TZ)


def to_local(dt: datetime) -> datetime:
    """Convert a UTC (or naive) datetime to Asia/Kolkata."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(APP_TZ)
