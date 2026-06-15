from __future__ import annotations
from datetime import date, datetime
from zoneinfo import ZoneInfo

DEFAULT_TIMEZONE = "America/New_York"


def local_today(tz_name: str | None = None) -> date:
    """Today's date in the user's timezone (defaults to ET).

    Lambda runs in UTC — date.today() there rolls over at 7/8pm ET, which puts
    evening logs on tomorrow's date. All "what day is it" decisions must go
    through this helper instead.
    """
    try:
        tz = ZoneInfo(tz_name or DEFAULT_TIMEZONE)
    except (KeyError, ValueError):
        tz = ZoneInfo(DEFAULT_TIMEZONE)
    return datetime.now(tz).date()


def protocol_today(protocol) -> date:
    """Today's date in the protocol's configured timezone."""
    return local_today(protocol.profile.timezone)
