"""When a saved report runs next.

Times are in the server's own zone (the operators' local time), and a run is
always in the future: a report never fires twice for one slot, and a server that
was down does not replay every missed day.
"""
from datetime import datetime, timedelta, timezone

import pytest

from app.services.report_schedule import is_valid, next_run

KST = timezone(timedelta(hours=9))


def at(y, m, d, h=0, mi=0):
    return datetime(y, m, d, h, mi, tzinfo=KST)


def test_daily_runs_today_if_the_hour_is_still_ahead():
    assert next_run("daily", 9, at(2026, 9, 30, 8, 0)) == at(2026, 9, 30, 9, 0)


def test_daily_runs_tomorrow_once_the_hour_has_passed():
    assert next_run("daily", 9, at(2026, 9, 30, 9, 0)) == at(2026, 10, 1, 9, 0)
    assert next_run("daily", 9, at(2026, 9, 30, 15, 30)) == at(2026, 10, 1, 9, 0)


def test_weekly_runs_on_the_chosen_weekday():
    # 2026-09-30 is a Wednesday; weekday 0 is Monday.
    assert next_run("weekly", 9, at(2026, 9, 30, 10), weekday=0) == at(2026, 10, 5, 9, 0)


def test_weekly_on_the_same_weekday_waits_a_week_once_past():
    assert next_run("weekly", 9, at(2026, 9, 30, 10), weekday=2) == at(2026, 10, 7, 9, 0)
    assert next_run("weekly", 9, at(2026, 9, 30, 8), weekday=2) == at(2026, 9, 30, 9, 0)


def test_monthly_runs_on_the_chosen_day():
    assert next_run("monthly", 9, at(2026, 9, 10, 10), day=15) == at(2026, 9, 15, 9, 0)
    assert next_run("monthly", 9, at(2026, 9, 20, 10), day=15) == at(2026, 10, 15, 9, 0)


def test_monthly_rolls_over_the_year():
    assert next_run("monthly", 9, at(2026, 12, 20, 10), day=15) == at(2027, 1, 15, 9, 0)


def test_the_result_is_always_after_the_moment_given():
    now = at(2026, 9, 30, 9, 0)
    for frequency in ("daily", "weekly", "monthly"):
        assert next_run(frequency, 9, now, weekday=2, day=30) > now


def test_the_time_zone_of_the_input_is_kept():
    assert next_run("daily", 9, at(2026, 9, 30, 8)).utcoffset() == timedelta(hours=9)


def test_validity_of_a_schedule():
    assert is_valid("daily", 9, None, None)
    assert is_valid("weekly", 0, 6, None)
    assert is_valid("monthly", 23, None, 28)
    assert not is_valid("hourly", 9, None, None)
    assert not is_valid("daily", 24, None, None)
    assert not is_valid("weekly", 9, 7, None)
    assert not is_valid("weekly", 9, None, None)
    # Days past 28 do not exist every month, so a report could silently skip.
    assert not is_valid("monthly", 9, None, 31)
    assert not is_valid("monthly", 9, None, None)


def test_an_unknown_frequency_is_refused_by_next_run():
    with pytest.raises(ValueError):
        next_run("yearly", 9, at(2026, 9, 30))
