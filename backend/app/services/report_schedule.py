"""When a saved report runs next."""
from datetime import datetime, timedelta
from typing import Optional

FREQUENCIES = ("daily", "weekly", "monthly")
# Past the 28th a day is missing in some months, and the report would skip.
MAX_MONTH_DAY = 28


def is_valid(frequency: str, hour: int, weekday: Optional[int], day: Optional[int]) -> bool:
    if frequency not in FREQUENCIES or not 0 <= hour <= 23:
        return False
    if frequency == "weekly":
        return weekday is not None and 0 <= weekday <= 6
    if frequency == "monthly":
        return day is not None and 1 <= day <= MAX_MONTH_DAY
    return True


def next_run(
    frequency: str,
    hour: int,
    after: datetime,
    weekday: Optional[int] = None,
    day: Optional[int] = None,
) -> datetime:
    """The first scheduled moment strictly after `after`, in its own time zone."""
    if frequency not in FREQUENCIES:
        raise ValueError(f"unknown frequency: {frequency}")

    slot = after.replace(hour=hour, minute=0, second=0, microsecond=0)

    if frequency == "daily":
        return slot if slot > after else slot + timedelta(days=1)

    if frequency == "weekly":
        ahead = ((weekday or 0) - slot.weekday()) % 7
        candidate = slot + timedelta(days=ahead)
        return candidate if candidate > after else candidate + timedelta(days=7)

    candidate = slot.replace(day=day or 1)
    if candidate > after:
        return candidate
    year, month = (slot.year + 1, 1) if slot.month == 12 else (slot.year, slot.month + 1)
    return slot.replace(year=year, month=month, day=day or 1)
