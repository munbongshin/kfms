"""Finer control over the four rules: per-category amounts, weekend / holiday /
night switched separately, and split payments by total and time window.

Every new parameter defaults to the old behaviour when absent, so the existing
rule tests and any stored settings keep working.
"""
from decimal import Decimal

from app.anomaly.rules import (
    SOURCES,
    detect_high_amount,
    detect_off_hours,
    detect_split_payment,
)

COLUMNS = SOURCES["approval"].columns
BILL_COLUMNS = SOURCES["bill"].columns


def params(code, **extra):
    return {"columns": COLUMNS, "code": code, "severity": "medium", **extra}


_seq = iter(range(1000, 100000))


def row(**overrides):
    defaults = dict(
        seq=Decimal(next(_seq)),
        **{"class": "A"},
        cardno="4072855739182287",
        merchno="000049877848",
        merchbizno="1010497150",
        merchname="상패프로",
        mccname="일반한식",
        transdate="2023-07-31",  # a Monday
        transtime="11:25:47",
        apprtot=Decimal("100000"),
    )
    defaults.update(overrides)
    return defaults


# --- amount by category -------------------------------------------------------------------------

HIGH = dict(threshold=Decimal("500000"))


def test_a_category_can_have_its_own_lower_threshold():
    p = params("HIGH_AMOUNT", **HIGH, category_thresholds={"영화관": Decimal("100000")})
    found = detect_high_amount([row(mccname="영화관", apprtot=Decimal("120000"))], p)
    assert len(found) == 1


def test_other_categories_keep_the_default_threshold():
    p = params("HIGH_AMOUNT", **HIGH, category_thresholds={"영화관": Decimal("100000")})
    assert detect_high_amount([row(mccname="일반한식", apprtot=Decimal("120000"))], p) == []


def test_a_category_threshold_can_be_higher_than_the_default():
    p = params("HIGH_AMOUNT", **HIGH, category_thresholds={"항공사": Decimal("2000000")})
    assert detect_high_amount([row(mccname="항공사", apprtot=Decimal("900000"))], p) == []
    assert len(detect_high_amount([row(mccname="항공사", apprtot=Decimal("2000000"))], p)) == 1


def test_the_summary_says_which_threshold_applied():
    p = params("HIGH_AMOUNT", **HIGH, category_thresholds={"영화관": Decimal("100000")})
    found = detect_high_amount([row(mccname="영화관", apprtot=Decimal("120000"))], p)
    assert "영화관" in found[0].summary and "100,000원" in found[0].summary


def test_without_category_thresholds_nothing_changes():
    p = params("HIGH_AMOUNT", **HIGH)
    assert len(detect_high_amount([row(apprtot=Decimal("500000"))], p)) == 1


def test_a_source_without_categories_uses_the_default():
    # v_bill has no mccname; the rule must not fail there.
    p = {"columns": BILL_COLUMNS, "code": "BILL_HIGH_AMOUNT", "severity": "high", **HIGH,
         "category_thresholds": {"영화관": Decimal("100000")}}
    bill = {"seq": Decimal(1), "class": "A", "orgnapprdate": "2023-07-31", "biltot": Decimal("600000"), "cardno": "1"}
    assert len(detect_high_amount([bill], p)) == 1


# --- off hours ------------------------------------------------------------------------------------

OFF = dict(night_start="23", night_end="06")
SATURDAY = "2023-07-29"
MONDAY = "2023-07-31"


def test_weekend_can_be_switched_off_on_its_own():
    p = params("OFF_HOURS", **OFF, check_weekend=False)
    assert detect_off_hours([row(transdate=SATURDAY, transtime="14:00:00")], p) == []
    # night still works
    assert len(detect_off_hours([row(transdate=MONDAY, transtime="23:30:00")], p)) == 1


def test_night_can_be_switched_off_on_its_own():
    p = params("OFF_HOURS", **OFF, check_night=False)
    assert detect_off_hours([row(transdate=MONDAY, transtime="23:30:00")], p) == []
    assert len(detect_off_hours([row(transdate=SATURDAY, transtime="14:00:00")], p)) == 1


def test_a_listed_holiday_counts_as_off_hours():
    p = params("OFF_HOURS", **OFF, holidays=["2023-08-15"])
    found = detect_off_hours([row(transdate="2023-08-15", transtime="14:00:00")], p)  # a Tuesday
    assert len(found) == 1 and "공휴일" in found[0].summary


def test_holidays_can_be_switched_off_though_listed():
    p = params("OFF_HOURS", **OFF, holidays=["2023-08-15"], check_holiday=False)
    assert detect_off_hours([row(transdate="2023-08-15", transtime="14:00:00")], p) == []


def test_a_holiday_on_a_weekend_is_called_a_holiday():
    p = params("OFF_HOURS", **OFF, holidays=[SATURDAY])
    found = detect_off_hours([row(transdate=SATURDAY, transtime="14:00:00")], p)
    assert "공휴일" in found[0].summary


def test_an_ordinary_weekday_daytime_is_never_flagged():
    p = params("OFF_HOURS", **OFF, holidays=["2023-08-15"])
    assert detect_off_hours([row(transdate=MONDAY, transtime="14:00:00")], p) == []


def test_off_hours_without_the_new_parameters_behaves_as_before():
    p = params("OFF_HOURS", **OFF)
    assert len(detect_off_hours([row(transdate=SATURDAY, transtime="14:00:00")], p)) == 1
    assert len(detect_off_hours([row(transdate=MONDAY, transtime="23:30:00")], p)) == 1


# --- split payments --------------------------------------------------------------------------------

SPLIT = dict(min_count=2, exclude_merchbizno=[])


def test_a_minimum_total_ignores_small_repeat_purchases():
    p = params("SPLIT_PAYMENT", **SPLIT, min_total=300000)
    small = [row(apprtot=Decimal("50000")), row(apprtot=Decimal("60000"))]
    assert detect_split_payment(small, p) == []


def test_a_group_reaching_the_minimum_total_is_flagged():
    p = params("SPLIT_PAYMENT", **SPLIT, min_total=300000)
    big = [row(apprtot=Decimal("200000")), row(apprtot=Decimal("150000"))]
    assert len(detect_split_payment(big, p)) == 1


def test_a_window_only_groups_payments_close_in_time():
    p = params("SPLIT_PAYMENT", **SPLIT, window_minutes=30)
    apart = [row(transtime="09:00:00"), row(transtime="15:00:00")]
    assert detect_split_payment(apart, p) == []


def test_payments_within_the_window_are_grouped():
    p = params("SPLIT_PAYMENT", **SPLIT, window_minutes=30)
    close = [row(transtime="09:00:00"), row(transtime="09:20:00")]
    found = detect_split_payment(close, p)
    assert len(found) == 1 and len(found[0].transactions) == 2


def test_the_window_chains_from_one_payment_to_the_next():
    p = params("SPLIT_PAYMENT", **{**SPLIT, "min_count": 3}, window_minutes=30)
    chain = [row(transtime="09:00:00"), row(transtime="09:25:00"), row(transtime="09:50:00")]
    assert len(detect_split_payment(chain, p)) == 1


def test_two_bursts_on_one_day_are_two_findings_with_distinct_keys():
    p = params("SPLIT_PAYMENT", **SPLIT, window_minutes=30)
    bursts = [row(transtime="09:00:00"), row(transtime="09:10:00"), row(transtime="15:00:00"), row(transtime="15:05:00")]
    found = detect_split_payment(bursts, p)
    assert len(found) == 2
    assert len({f.finding_key for f in found}) == 2


def test_without_a_window_the_key_is_the_old_one():
    p = params("SPLIT_PAYMENT", **SPLIT)
    found = detect_split_payment([row(), row()], p)
    assert found[0].finding_key == "SPLIT_PAYMENT:4072855739182287|000049877848|2023-07-31"


def test_a_source_without_time_ignores_the_window():
    # v_bill has no time of day; grouping falls back to the whole day.
    p = {"columns": BILL_COLUMNS, "code": "BILL_SPLIT_PAYMENT", "severity": "medium", **SPLIT, "window_minutes": 30}
    assert detect_split_payment([], p) == []
