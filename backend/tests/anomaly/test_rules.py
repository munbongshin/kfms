from decimal import Decimal

from app.anomaly.rules import detect_high_amount


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
