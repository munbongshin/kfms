"""A rule the administrator switched off is still listed, but never run."""
from decimal import Decimal

from app.anomaly.rules import SOURCES, TEMPLATES, build_rules
from app.anomaly.settings import apply_overrides
from app.services.anomaly_service import AnomalyService


def approvals_rows():
    return [{
        "seq": Decimal(1), "class": "A", "transdate": "2023-07-29", "transtime": "14:00:00",
        "apprtot": Decimal("900000"), "cardno": "1", "merchno": "m", "merchbizno": "b",
        "mccname": "영화관", "merchname": "x",
    }]


def run(overrides):
    rules = [r for r in build_rules(SOURCES, apply_overrides(TEMPLATES, overrides)) if r.source == "approval"]
    service = AnomalyService(pool=None, repo=None, rules=rules)
    applicable, findings = [], []
    service._run_source_rules("1", rules, approvals_rows(), None, applicable, findings)
    return applicable, findings


def test_with_no_changes_every_rule_runs():
    applicable, findings = run({})
    assert {f.rule_code for f in findings} == {"HIGH_AMOUNT", "OFF_HOURS", "WATCH_MCC"}
    assert all(a["applicable"] for a in applicable)


def test_a_switched_off_rule_finds_nothing_and_says_why():
    applicable, findings = run({"HIGH_AMOUNT": {"enabled": False}})
    assert "HIGH_AMOUNT" not in {f.rule_code for f in findings}
    off = next(a for a in applicable if a["template"] == "HIGH_AMOUNT")
    assert off["applicable"] is False and "껐습니다" in off["caveat"]


def test_the_other_rules_still_run_when_one_is_off():
    _, findings = run({"HIGH_AMOUNT": {"enabled": False}})
    assert {f.rule_code for f in findings} == {"OFF_HOURS", "WATCH_MCC"}


def test_a_changed_severity_is_what_the_finding_carries():
    _, findings = run({"OFF_HOURS": {"severity": "high"}})
    assert next(f for f in findings if f.rule_code == "OFF_HOURS").severity == "high"
