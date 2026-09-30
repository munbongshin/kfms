"""Korean public holidays, applied automatically to the off-hours rule.

Two automatic sources are combined:

* the built-in calendar from the `holidays` package (lunar holidays, substitute
  holidays, temporary holidays it already knows), and
* days received by the sync (`holiday_sources`), which is how a 임시공휴일
  announced after the package was released gets picked up.

An administrator can add days on top (a company holiday) and remove automatic
ones (a day the office works).
"""
import logging
from datetime import date
from functools import lru_cache
from typing import Any, Dict, Iterable, List, Mapping, Optional

logger = logging.getLogger(__name__)

WEEKDAYS = ("월", "화", "수", "목", "금", "토", "일")


@lru_cache(maxsize=32)
def public_holidays(year: int) -> Dict[str, str]:
    """ISO date -> Korean name from the built-in calendar. Empty if it is unavailable."""
    try:
        import holidays

        found = holidays.country_holidays("KR", years=year, language="ko")
    except Exception:
        logger.exception("Korean holiday calendar unavailable for %s", year)
        return {}
    return {day.isoformat(): name for day, name in sorted(found.items())}


def calendar_version() -> str:
    """The version of the built-in calendar, for the screen."""
    try:
        import holidays

        return str(holidays.__version__)
    except Exception:
        return ""


def _automatic(day: str, synced: Optional[Mapping[str, str]]) -> Optional[str]:
    """The name of an automatic holiday, synced first (it is the newer source)."""
    return (synced or {}).get(day) or public_holidays(int(day[:4])).get(day)


def holiday_of(
    day: str,
    auto: bool,
    extra: Iterable[str],
    exceptions: Iterable[str],
    synced: Optional[Mapping[str, str]] = None,
) -> Optional[str]:
    """The holiday `day` (YYYY-MM-DD) falls on, or None.

    "" means a day the administrator added, which has no official name. Removing a
    day only cancels an automatic holiday; one added by hand stays.
    """
    if day in set(extra):
        return ""
    if auto and day not in set(exceptions):
        return _automatic(day, synced)
    return None


def calendar(
    year: int,
    auto: bool,
    extra: Iterable[str],
    exceptions: Iterable[str],
    synced: Optional[Mapping[str, str]] = None,
) -> List[Dict[str, Any]]:
    """Every holiday of `year` under these settings, for the screen to show.

    An automatic holiday the administrator removed stays listed, marked
    excluded, so it is clear why it no longer counts. `new` marks a day only the
    sync knows: it was declared after the built-in calendar was made.
    """
    removed = set(exceptions)
    package = public_holidays(year)
    received = {d: n for d, n in (synced or {}).items() if d[:4] == str(year)}
    rows: Dict[str, Dict[str, Any]] = {}

    if auto:
        for day in sorted(set(package) | set(received)):
            name = received.get(day) or package.get(day, "")
            rows[day] = {
                "date": day,
                "name": name,
                "source": "synced" if day in received else "auto",
                "excluded": day in removed,
                "in_package": day in package,
                "in_synced": day in received,
                "new": day in received and day not in package,
                "temporary": "임시" in name,
            }

    for day in {d for d in extra if d[:4] == str(year)}:
        # A day added by hand that is also official is listed once, as added.
        name = rows.get(day, {}).get("name", "")
        rows[day] = {
            "date": day, "name": name, "source": "extra", "excluded": False,
            "in_package": day in package, "in_synced": day in received,
            "new": False, "temporary": "임시" in name,
        }

    return [rows[d] for d in sorted(rows)]


def check_day(
    day: str,
    auto: bool,
    extra: Iterable[str],
    exceptions: Iterable[str],
    synced: Optional[Mapping[str, str]] = None,
) -> Dict[str, Any]:
    """Whether `day` is counted as a holiday, and why — in words for the screen."""
    weekday = WEEKDAYS[date.fromisoformat(day).weekday()]
    known = _automatic(day, synced)
    in_package = day[:4].isdigit() and day in public_holidays(int(day[:4]))
    in_synced = day in (synced or {})
    base = {"date": day, "weekday": weekday}

    if day in set(extra):
        return {**base, "holiday": True, "name": known or "", "reason": "included_extra",
                "message": "추가 공휴일로 등록되어 있어 공휴일로 봅니다"}
    if known and not auto:
        return {**base, "holiday": False, "name": known, "reason": "auto_off",
                "message": f"{known} — 법정 공휴일이지만 '법정 공휴일 자동 적용'이 꺼져 있어 공휴일로 보지 않습니다"}
    if known and day in set(exceptions):
        return {**base, "holiday": False, "name": known, "reason": "excluded",
                "message": f"{known} — 자동 공휴일이지만 '제외할 날짜'에 있어 근무일로 봅니다"}
    if known:
        if in_synced and not in_package:
            where = "동기화로 새로 받은 공휴일입니다 (내장 달력에는 아직 없음)"
        elif in_synced:
            where = "내장 달력과 동기화한 목록 모두에 있습니다"
        else:
            where = "내장 달력에 있습니다"
        return {**base, "holiday": True, "name": known, "reason": "included_auto",
                "message": f"공휴일에 포함되어 있습니다 — {known} ({where})"}
    return {**base, "holiday": False, "name": "", "reason": "not_found",
            "message": "공휴일 목록에 없습니다. 방금 발표된 임시공휴일이라면 '지금 동기화'로 받아 보거나 '추가 공휴일'로 등록하세요"}
