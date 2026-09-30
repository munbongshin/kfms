"""Editing the anomaly thresholds without touching code.

Only a fixed set of numbers and lists can be changed — the amount that counts
as 고액, the night hours, the watched merchant categories, how many same-day
payments look like splitting. Everything is checked before it is stored, so a
typo cannot silently switch a rule off.
"""
from decimal import Decimal

from app.anomaly.rules import SOURCES, TEMPLATES, build_rules
from app.anomaly.settings import apply_overrides, describe, validate


def params_of(templates, name):
    return next(t for t in templates if t.template == name).params


# --- validate ---------------------------------------------------------------

def test_good_values_are_accepted_and_normalised():
    clean, errors = validate({
        "HIGH_AMOUNT": {"threshold": "300000"},
        "OFF_HOURS": {"night_start": 22, "night_end": 5},
        "SPLIT_PAYMENT": {"min_count": "3"},
    })
    assert errors == []
    assert clean["HIGH_AMOUNT"]["threshold"] == 300000
    assert clean["OFF_HOURS"] == {"night_start": "22", "night_end": "05"}
    assert clean["SPLIT_PAYMENT"]["min_count"] == 3


def test_a_zero_or_negative_amount_is_refused():
    for bad in (0, -5, "abc", None, 10 ** 13):
        _, errors = validate({"HIGH_AMOUNT": {"threshold": bad}})
        assert errors, bad


def test_hours_must_be_real_hours():
    _, errors = validate({"OFF_HOURS": {"night_start": 24, "night_end": 5}})
    assert errors
    _, errors = validate({"OFF_HOURS": {"night_start": 22, "night_end": -1}})
    assert errors


def test_split_needs_at_least_two_payments():
    _, errors = validate({"SPLIT_PAYMENT": {"min_count": 1}})
    assert errors


def test_lists_are_trimmed_deduplicated_and_blank_free():
    clean, errors = validate({"WATCH_MCC": {"watch_mcc": ["  영화관 ", "영화관", "", "볼 링 장"]}})
    assert errors == []
    assert clean["WATCH_MCC"]["watch_mcc"] == ["영화관", "볼 링 장"]


def test_an_empty_watch_list_is_refused():
    # An empty list would quietly switch the rule off.
    _, errors = validate({"WATCH_MCC": {"watch_mcc": ["", " "]}})
    assert errors


def test_unknown_rules_and_parameters_are_refused():
    _, errors = validate({"NOPE": {"x": 1}})
    assert errors
    _, errors = validate({"HIGH_AMOUNT": {"columns": {}}})
    assert errors


# --- apply ------------------------------------------------------------------

def test_no_overrides_leaves_the_defaults():
    assert apply_overrides(TEMPLATES, {}) == TEMPLATES


def test_an_override_replaces_only_that_parameter():
    out = apply_overrides(TEMPLATES, {"HIGH_AMOUNT": {"threshold": 300000}})
    assert params_of(out, "HIGH_AMOUNT")["threshold"] == Decimal("300000")
    assert params_of(out, "OFF_HOURS") == params_of(TEMPLATES, "OFF_HOURS")


def test_the_original_templates_are_not_modified():
    apply_overrides(TEMPLATES, {"HIGH_AMOUNT": {"threshold": 1}})
    assert params_of(TEMPLATES, "HIGH_AMOUNT")["threshold"] == Decimal("500000")


def test_overridden_templates_still_bind_to_sources():
    out = apply_overrides(TEMPLATES, {"HIGH_AMOUNT": {"threshold": 300000}})
    rules = build_rules(SOURCES, out)
    high = [r for r in rules if r.template == "HIGH_AMOUNT"]
    assert high and all(r.params["threshold"] == Decimal("300000") for r in high)


# --- describe ---------------------------------------------------------------

def test_the_screen_gets_every_editable_parameter_with_its_default():
    info = describe(TEMPLATES, {"HIGH_AMOUNT": {"threshold": 300000}})
    high = next(t for t in info if t["template"] == "HIGH_AMOUNT")
    param = next(p for p in high["params"] if p["key"] == "threshold")
    assert param["key"] == "threshold"
    assert param["value"] == 300000
    assert param["default"] == 500000
    assert param["kind"] == "number"


def test_describe_lists_all_four_rules():
    names = [t["template"] for t in describe(TEMPLATES, {})]
    assert names == ["HIGH_AMOUNT", "OFF_HOURS", "WATCH_MCC", "SPLIT_PAYMENT"]
