from datetime import date, datetime, timezone
from decimal import Decimal

from app.anomaly.models import Finding
from app.services.anomaly_service import merge_reviews


class FakeReview:
    def __init__(self, status, fingerprint, note=None):
        self.status = status
        self.fingerprint = fingerprint
        self.note = note
        self.reviewed_at = datetime(2026, 9, 22, tzinfo=timezone.utc)


def finding(**overrides):
    defaults = dict(
        rule_code="SPLIT_PAYMENT",
        subject="CARD|MERCH|2023-07-31",
        severity="medium",
        summary="동일 가맹점 당일 2건 204,000원",
        transactions=[{"seq": Decimal("1")}, {"seq": Decimal("2")}],
        amount=Decimal("204000"),
        occurred_on=date(2023, 7, 31),
    )
    defaults.update(overrides)
    return Finding(**defaults)


def test_unreviewed_finding_has_no_review_and_is_not_stale():
    merged = merge_reviews([finding()], {})
    assert merged[0]["review"] is None
    assert merged[0]["stale"] is False


def test_review_with_matching_fingerprint_is_not_stale():
    f = finding()
    merged = merge_reviews([f], {f.finding_key: FakeReview("dismissed", f.fingerprint)})
    assert merged[0]["review"]["status"] == "dismissed"
    assert merged[0]["stale"] is False


def test_review_goes_stale_when_the_group_grows():
    reviewed = finding()
    grown = finding(
        transactions=[{"seq": Decimal("1")}, {"seq": Decimal("2")}, {"seq": Decimal("3")}],
        amount=Decimal("304000"),
    )
    merged = merge_reviews([grown], {reviewed.finding_key: FakeReview("dismissed", reviewed.fingerprint)})
    assert merged[0]["stale"] is True
