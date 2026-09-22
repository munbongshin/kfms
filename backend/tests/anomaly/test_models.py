from datetime import date
from decimal import Decimal

from app.anomaly.models import Finding


def _finding(**overrides):
    defaults = dict(
        rule_code="HIGH_AMOUNT",
        subject="560348",
        severity="high",
        summary="단건 5,850,000원",
        transactions=[{"seq": Decimal("560348"), "apprtot": Decimal("5850000.00")}],
        amount=Decimal("5850000.00"),
        occurred_on=date(2023, 7, 3),
    )
    defaults.update(overrides)
    return Finding(**defaults)


def test_finding_key_joins_rule_and_subject():
    assert _finding().finding_key == "HIGH_AMOUNT:560348"


def test_fingerprint_changes_when_a_transaction_is_added_with_total_held_constant():
    one = _finding(
        transactions=[{"seq": Decimal("560348"), "apprtot": Decimal("5850000.00")}],
        amount=Decimal("5850000.00"),
    )
    two = _finding(
        transactions=[
            {"seq": Decimal("560348"), "apprtot": Decimal("5849000.00")},
            {"seq": Decimal("560349"), "apprtot": Decimal("1000.00")},
        ],
        amount=Decimal("5850000.00"),
    )
    assert one.fingerprint != two.fingerprint


def test_fingerprint_changes_when_the_total_changes_with_transaction_set_held_constant():
    one = _finding(
        transactions=[{"seq": Decimal("560348"), "apprtot": Decimal("5850000.00")}],
        amount=Decimal("5850000.00"),
    )
    two = _finding(
        transactions=[{"seq": Decimal("560348"), "apprtot": Decimal("5851000.00")}],
        amount=Decimal("5851000.00"),
    )
    assert one.fingerprint != two.fingerprint


def test_fingerprint_changes_when_a_transaction_is_swapped_for_an_equal_value_one():
    one = _finding(
        transactions=[{"seq": Decimal("560348"), "apprtot": Decimal("5850000.00")}],
        amount=Decimal("5850000.00"),
    )
    two = _finding(
        transactions=[{"seq": Decimal("560999"), "apprtot": Decimal("5850000.00")}],
        amount=Decimal("5850000.00"),
    )
    assert one.fingerprint != two.fingerprint


def test_fingerprint_is_stable_for_the_same_content():
    assert _finding().fingerprint == _finding().fingerprint
