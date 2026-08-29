from __future__ import annotations

from datetime import datetime, timezone


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def ensure_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("datetimes must be timezone-aware")
    return value.astimezone(timezone.utc)


def isoformat(value: datetime | None) -> str | None:
    value = ensure_utc(value)
    return value.isoformat(timespec="microseconds").replace("+00:00", "Z") if value else None


def parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return ensure_utc(parsed)

