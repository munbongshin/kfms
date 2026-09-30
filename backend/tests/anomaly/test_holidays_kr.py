"""Korean public holidays are applied automatically, and the administrator can
add days (a company holiday) or remove automatic ones (a working day).
"""
from decimal import Decimal

from app.anomaly.holidays_kr import calendar, holiday_of, public_holidays
from app.anomaly.rules import SOURCES, detect_off_hours

COLUMNS = SOURCES["approval"].columns


# --- the built-in calendar ----------------------------------------------------------------------

def test_fixed_date_holidays_are_known():
    days = public_holidays(2023)
    assert "2023-08-15" in days and "2023-06-06" in days and "2023-12-25" in days


def test_lunar_holidays_are_worked_out_for_the_year():
    assert "2026-09-25" in public_holidays(2026)  # 추석
    assert "2026-02-17" in public_holidays(2026)  # 설날


def test_substitute_and_temporary_holidays_are_included():
    days = public_holidays(2023)
    assert "2023-05-29" in days  # 부처님오신날 대체공휴일
    assert "2023-10-02" in days  # 임시공휴일


def test_names_are_in_korean():
    assert "광복절" in public_holidays(2023)["2023-08-15"]


def test_an_ordinary_day_is_not_a_holiday():
    assert "2023-07-31" not in public_holidays(2023)


# --- what applies -----------------------------------------------------------------------------------

def test_an_automatic_holiday_applies_by_default():
    assert "광복절" in holiday_of("2023-08-15", auto=True, extra=[], exceptions=[])


def test_automatic_holidays_can_be_switched_off():
    assert holiday_of("2023-08-15", auto=False, extra=[], exceptions=[]) is None


def test_an_extra_day_is_a_holiday_too_and_has_no_official_name():
    assert holiday_of("2023-07-31", auto=True, extra=["2023-07-31"], exceptions=[]) == ""


def test_an_exception_removes_an_automatic_holiday():
    assert holiday_of("2023-08-15", auto=True, extra=[], exceptions=["2023-08-15"]) is None


def test_an_exception_does_not_cancel_a_day_added_by_hand():
    assert holiday_of("2023-07-31", auto=True, extra=["2023-07-31"], exceptions=["2023-07-31"]) == ""


def test_extra_days_work_with_the_automatic_ones_off():
    assert holiday_of("2023-07-31", auto=False, extra=["2023-07-31"], exceptions=[]) == ""


# --- the year view shown to the administrator ---------------------------------------------------------

def test_the_year_lists_automatic_holidays_in_date_order():
    rows = calendar(2023, auto=True, extra=[], exceptions=[])
    dates = [r["date"] for r in rows]
    assert dates == sorted(dates) and "2023-08-15" in dates
    assert all(r["source"] == "auto" and r["excluded"] is False for r in rows)


def test_an_excluded_day_stays_listed_but_marked():
    rows = {r["date"]: r for r in calendar(2023, auto=True, extra=[], exceptions=["2023-08-15"])}
    assert rows["2023-08-15"]["excluded"] is True


def test_extra_days_of_that_year_are_listed_as_added():
    rows = {r["date"]: r for r in calendar(2023, auto=True, extra=["2023-07-31", "2024-01-02"], exceptions=[])}
    assert rows["2023-07-31"]["source"] == "extra"
    assert "2024-01-02" not in rows  # another year


def test_with_automatic_holidays_off_only_the_added_days_are_listed():
    rows = calendar(2023, auto=False, extra=["2023-07-31"], exceptions=[])
    assert [r["date"] for r in rows] == ["2023-07-31"]


def test_a_day_added_by_hand_that_is_also_official_is_listed_once():
    rows = [r for r in calendar(2023, auto=True, extra=["2023-08-15"], exceptions=[]) if r["date"] == "2023-08-15"]
    assert len(rows) == 1


# --- in the off-hours rule -----------------------------------------------------------------------------

def params(**extra):
    return {"columns": COLUMNS, "code": "OFF_HOURS", "severity": "medium",
            "night_start": "23", "night_end": "06", **extra}


def approval(day, clock="14:00:00"):
    return {"seq": Decimal(1), "class": "A", "transdate": day, "transtime": clock, "apprtot": Decimal("1000")}


TUESDAY_HOLIDAY = "2023-08-15"


def test_an_official_holiday_is_flagged_without_listing_it():
    found = detect_off_hours([approval(TUESDAY_HOLIDAY)], params())
    assert len(found) == 1 and "공휴일" in found[0].summary and "광복절" in found[0].summary


def test_automatic_holidays_switched_off_stop_flagging_it():
    assert detect_off_hours([approval(TUESDAY_HOLIDAY)], params(auto_holidays=False)) == []


def test_an_excluded_day_is_treated_as_a_working_day():
    assert detect_off_hours([approval(TUESDAY_HOLIDAY)], params(holiday_exceptions=[TUESDAY_HOLIDAY])) == []


def test_a_company_holiday_is_flagged():
    found = detect_off_hours([approval("2023-07-31")], params(holidays=["2023-07-31"]))
    assert len(found) == 1 and "공휴일" in found[0].summary


def test_the_holiday_check_switch_still_turns_all_of_it_off():
    assert detect_off_hours([approval(TUESDAY_HOLIDAY)], params(check_holiday=False)) == []
