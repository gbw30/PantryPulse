"""Pure operational calendar/ownership checks; no database or inventory mutation."""

from datetime import date, datetime
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


def local_day(instant: datetime, timezone: str) -> date:
    if instant.tzinfo is None or instant.utcoffset() is None:
        raise ValueError("operational timestamps require an explicit timezone offset")
    try:
        zone = ZoneInfo(timezone)
    except (ZoneInfoNotFoundError, ValueError) as error:
        raise ValueError("unknown operational timezone") from error
    return instant.astimezone(zone).date()


def require_same_organization(expected: UUID, *referenced: UUID) -> None:
    """Repository passes the actual organization IDs loaded for referenced records."""
    if not isinstance(expected, UUID) or any(not isinstance(item, UUID) for item in referenced):
        raise TypeError("organization identifiers must be UUID instances")
    if any(item != expected for item in referenced):
        raise ValueError("cross-organization reference is forbidden")
