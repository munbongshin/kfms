from decimal import Decimal

from app.anomaly.rules import detect_high_amount, detect_off_hours, detect_watch_mcc


def row(**overrides):
    defaults = dict(
        seq=Decimal("560348"),
        **{"class": "A"},
        cardno="4072855739182287",
        merchno="000049877848",
        merchbizno="1010497150",
        merchname="상패프로",
        mccname="일반한식",
        transdate="2023-07-31",
        transtime="11:25:47",
        apprtot=Decimal("100000.00"),
    )
    defaults.update(overrides)
    return defaults


def test_high_amount_flags_at_the_threshold():
    findings = detect_high_amount([row(apprtot=Decimal("500000"))], {"threshold": Decimal("500000")})
    assert len(findings) == 1
    assert findings[0].finding_key == "HIGH_AMOUNT:560348"


def test_high_amount_ignores_one_won_below_the_threshold():
    findings = detect_high_amount([row(apprtot=Decimal("499999"))], {"threshold": Decimal("500000")})
    assert findings == []


def test_high_amount_ignores_cancellations():
    cancelled = row(apprtot=Decimal("900000"), **{"class": "B"})
    assert detect_high_amount([cancelled], {"threshold": Decimal("500000")}) == []


OFF_HOURS_PARAMS = {"night_start": "23", "night_end": "06"}


def test_off_hours_flags_saturday():
    # 2023-07-29 is a Saturday.
    findings = detect_off_hours([row(transdate="2023-07-29", transtime="14:30:00")], OFF_HOURS_PARAMS)
    assert len(findings) == 1
    assert "토요일" in findings[0].summary


def test_off_hours_ignores_a_weekday_daytime_payment():
    # 2023-07-28 is a Friday.
    assert detect_off_hours([row(transdate="2023-07-28", transtime="14:30:00")], OFF_HOURS_PARAMS) == []


def test_off_hours_boundary_2259_is_not_night():
    assert detect_off_hours([row(transdate="2023-07-28", transtime="22:59:59")], OFF_HOURS_PARAMS) == []


def test_off_hours_boundary_2300_is_night():
    assert len(detect_off_hours([row(transdate="2023-07-28", transtime="23:00:00")], OFF_HOURS_PARAMS)) == 1


def test_off_hours_boundary_0559_is_night():
    assert len(detect_off_hours([row(transdate="2023-07-28", transtime="05:59:59")], OFF_HOURS_PARAMS)) == 1


def test_off_hours_boundary_0600_is_not_night():
    assert detect_off_hours([row(transdate="2023-07-28", transtime="06:00:00")], OFF_HOURS_PARAMS) == []


def test_off_hours_ignores_cancellations():
    cancelled = row(transdate="2023-07-29", transtime="14:30:00", **{"class": "B"})
    assert detect_off_hours([cancelled], OFF_HOURS_PARAMS) == []


WATCH_PARAMS = {"watch_mcc": ["상품권 전문판매", "영화관"]}


def test_watch_mcc_flags_a_listed_category():
    findings = detect_watch_mcc([row(mccname="상품권 전문판매")], WATCH_PARAMS)
    assert len(findings) == 1
    assert findings[0].summary == "주의 업종: 상품권 전문판매"


def test_watch_mcc_ignores_an_unlisted_category():
    assert detect_watch_mcc([row(mccname="일반한식")], WATCH_PARAMS) == []


def test_watch_mcc_ignores_null_category():
    # 43 of 190 approvals have no mccname; they must not raise.
    assert detect_watch_mcc([row(mccname=None)], WATCH_PARAMS) == []


def test_watch_mcc_ignores_cancellations():
    cancelled = row(mccname="영화관", **{"class": "B"})
    assert detect_watch_mcc([cancelled], WATCH_PARAMS) == []
