"""Holidays received from outside (announced 임시공휴일) join the built-in
calendar, and a date can be checked to see whether it is counted and why.
"""
from decimal import Decimal

from app.anomaly.holidays_kr import calendar, check_day, holiday_of
from app.anomaly.rules import SOURCES, detect_off_hours

NEW_DAY = "2026-07-01"          # an ordinary Wednesday the government might declare a holiday
SYNCED = {NEW_DAY: "임시공휴일", "2026-08-15": "광복절"}


# --- applying ---------------------------------------------------------------------------------------

def test_a_synced_day_is_a_holiday_even_though_the_built_in_calendar_lacks_it():
    assert holiday_of(NEW_DAY, auto=True, extra=[], exceptions=[]) is None
    assert holiday_of(NEW_DAY, auto=True, extra=[], exceptions=[], synced=SYNCED) == "임시공휴일"


def test_the_synced_name_is_preferred_when_both_have_the_day():
    assert holiday_of("2026-08-15", True, [], [], synced={"2026-08-15": "광복절(동기화)"}) == "광복절(동기화)"


def test_synced_days_follow_the_automatic_switch():
    assert holiday_of(NEW_DAY, auto=False, extra=[], exceptions=[], synced=SYNCED) is None


def test_an_exception_removes_a_synced_day_too():
    assert holiday_of(NEW_DAY, True, [], [NEW_DAY], synced=SYNCED) is None


# --- the year view ------------------------------------------------------------------------------------

def rows_of(**kw):
    return {r["date"]: r for r in calendar(2026, True, kw.get("extra", []), kw.get("exceptions", []), synced=SYNCED)}


def test_a_synced_only_day_is_listed_as_newly_reflected_and_temporary():
    row = rows_of()[NEW_DAY]
    assert row["source"] == "synced" and row["new"] is True and row["temporary"] is True
    assert row["in_package"] is False and row["in_synced"] is True


def test_a_day_in_both_is_not_new():
    row = rows_of()["2026-08-15"]
    assert row["new"] is False and row["in_package"] is True and row["in_synced"] is True


def test_a_built_in_only_day_stays_automatic():
    row = rows_of()["2026-09-25"]
    assert row["source"] == "auto" and row["in_synced"] is False


def test_a_temporary_holiday_in_the_built_in_calendar_is_marked_too():
    rows = {r["date"]: r for r in calendar(2023, True, [], [])}
    assert rows["2023-10-02"]["temporary"] is True
    assert rows["2023-08-15"]["temporary"] is False


def test_an_excluded_synced_day_stays_listed_and_marked():
    assert rows_of(exceptions=[NEW_DAY])[NEW_DAY]["excluded"] is True


# --- checking one date ---------------------------------------------------------------------------------

def check(day, **kw):
    kw.setdefault("auto", True)
    kw.setdefault("extra", [])
    kw.setdefault("exceptions", [])
    kw.setdefault("synced", SYNCED)
    return check_day(day, **kw)


def test_a_built_in_holiday_is_reported_included():
    r = check("2026-09-25", synced={})
    assert r["holiday"] is True and r["reason"] == "included_auto" and "추석" in r["name"]
    assert "내장" in r["message"]


def test_a_synced_only_day_says_it_came_from_the_sync():
    r = check(NEW_DAY)
    assert r["holiday"] is True and "동기화" in r["message"] and r["name"] == "임시공휴일"


def test_a_day_added_by_hand_is_reported_as_such():
    r = check("2026-07-02", extra=["2026-07-02"])
    assert r["holiday"] is True and r["reason"] == "included_extra"


def test_an_excluded_day_is_reported_as_a_working_day_with_the_reason():
    r = check(NEW_DAY, exceptions=[NEW_DAY])
    assert r["holiday"] is False and r["reason"] == "excluded"


def test_a_day_nobody_knows_says_what_to_do_about_it():
    r = check("2026-07-02")
    assert r["holiday"] is False and r["reason"] == "not_found"
    assert "동기화" in r["message"] and "추가 공휴일" in r["message"]


def test_with_automatic_holidays_off_a_known_day_is_reported_as_not_counted():
    r = check("2026-09-25", auto=False)
    assert r["holiday"] is False and r["reason"] == "auto_off"


def test_the_weekday_is_reported():
    assert check("2026-09-25")["weekday"] == "금"


# --- in the rule ------------------------------------------------------------------------------------------

def test_the_rule_uses_synced_holidays():
    params = {"columns": SOURCES["approval"].columns, "code": "OFF_HOURS", "severity": "medium",
              "night_start": "23", "night_end": "06", "synced_holidays": SYNCED}
    row = {"seq": Decimal(1), "class": "A", "transdate": NEW_DAY, "transtime": "14:00:00", "apprtot": Decimal("1")}
    found = detect_off_hours([row], params)
    assert len(found) == 1 and "임시공휴일" in found[0].summary
