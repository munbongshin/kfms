"""Finer anomaly settings: on/off and severity per rule, amounts by category,
weekend / holiday / night on their own, split payments by total and window.
"""
from decimal import Decimal

from app.anomaly.rules import SOURCES, TEMPLATES, build_rules
from app.anomaly.settings import apply_overrides, describe, validate


def params_of(templates, name):
    return next(t for t in templates if t.template == name).params


def one(info, template, key):
    rule = next(t for t in info if t["template"] == template)
    return next(p for p in rule["params"] if p["key"] == key)


def test_every_rule_can_be_switched_off_and_given_a_severity():
    info = describe(TEMPLATES, {})
    for template in ("HIGH_AMOUNT", "OFF_HOURS", "WATCH_MCC", "SPLIT_PAYMENT"):
        assert one(info, template, "enabled")["kind"] == "switch"
        assert one(info, template, "enabled")["value"] is True
        assert one(info, template, "severity")["kind"] == "choice"


def test_severity_defaults_to_the_rules_own_and_lists_its_choices():
    sev = one(describe(TEMPLATES, {}), "HIGH_AMOUNT", "severity")
    assert sev["default"] == "high" and sev["value"] == "high"
    assert [o["value"] for o in sev["options"]] == ["high", "medium", "low"]


def test_enabled_and_severity_are_validated():
    clean, errors = validate({"OFF_HOURS": {"enabled": False, "severity": "high"}})
    assert errors == [] and clean["OFF_HOURS"] == {"enabled": False, "severity": "high"}
    for bad in ({"enabled": "yes"}, {"enabled": 1}, {"severity": "urgent"}, {"severity": ""}):
        _, errors = validate({"OFF_HOURS": bad})
        assert errors, bad


def test_category_thresholds_are_cleaned_and_bounded():
    clean, errors = validate({"HIGH_AMOUNT": {"category_thresholds": {" 영화관 ": "100000", "항공사": 2000000}}})
    assert errors == []
    assert clean["HIGH_AMOUNT"]["category_thresholds"] == {"영화관": 100000, "항공사": 2000000}
    for bad in ({"영화관": 0}, {"영화관": "abc"}, {"": 5}, {"영화관": 10 ** 13}, ["영화관"]):
        _, errors = validate({"HIGH_AMOUNT": {"category_thresholds": bad}})
        assert errors, bad


def test_an_empty_category_table_is_fine():
    clean, errors = validate({"HIGH_AMOUNT": {"category_thresholds": {}}})
    assert errors == [] and clean["HIGH_AMOUNT"]["category_thresholds"] == {}


def test_holidays_must_be_real_dates_and_come_back_sorted_without_duplicates():
    clean, errors = validate({"OFF_HOURS": {"holidays": ["2023-10-03", " 2023-08-15 ", "2023-08-15"]}})
    assert errors == [] and clean["OFF_HOURS"]["holidays"] == ["2023-08-15", "2023-10-03"]
    for bad in (["2023-02-30"], ["15/08/2023"], ["abc"], "2023-08-15"):
        _, errors = validate({"OFF_HOURS": {"holidays": bad}})
        assert errors, bad


def test_off_hours_needs_at_least_one_check_left_on():
    # All three off, with the rule still enabled, would quietly find nothing.
    _, errors = validate({"OFF_HOURS": {"check_weekend": False, "check_holiday": False, "check_night": False}})
    assert errors
    _, errors = validate({"OFF_HOURS": {"check_weekend": False, "check_holiday": False, "check_night": True}})
    assert errors == []


def test_all_checks_off_is_fine_when_the_rule_itself_is_off():
    _, errors = validate({"OFF_HOURS": {
        "enabled": False, "check_weekend": False, "check_holiday": False, "check_night": False}})
    assert errors == []


def test_split_total_and_window_are_bounded_and_zero_means_off():
    clean, errors = validate({"SPLIT_PAYMENT": {"min_total": 0, "window_minutes": 0}})
    assert errors == [] and clean["SPLIT_PAYMENT"] == {"min_total": 0, "window_minutes": 0}
    for bad in ({"min_total": -1}, {"min_total": "x"}, {"window_minutes": -5}, {"window_minutes": 1441}):
        _, errors = validate({"SPLIT_PAYMENT": bad})
        assert errors, bad


def test_a_severity_override_reaches_the_bound_rules():
    out = apply_overrides(TEMPLATES, {"OFF_HOURS": {"severity": "high"}})
    off = [r for r in build_rules(SOURCES, out) if r.template == "OFF_HOURS"]
    assert off and all(r.severity == "high" and r.params["severity"] == "high" for r in off)


def test_enabled_reaches_the_rule_params():
    out = apply_overrides(TEMPLATES, {"WATCH_MCC": {"enabled": False}})
    rules = [r for r in build_rules(SOURCES, out) if r.template == "WATCH_MCC"]
    assert rules and all(r.params["enabled"] is False for r in rules)


def test_category_thresholds_become_decimals_for_the_rule():
    out = apply_overrides(TEMPLATES, {"HIGH_AMOUNT": {"category_thresholds": {"영화관": 100000}}})
    assert params_of(out, "HIGH_AMOUNT")["category_thresholds"] == {"영화관": Decimal("100000")}


def test_defaults_carry_every_new_parameter():
    off = params_of(TEMPLATES, "OFF_HOURS")
    assert off["check_weekend"] is True and off["check_night"] is True and off["check_holiday"] is True
    assert off["holidays"] == []
    split = params_of(TEMPLATES, "SPLIT_PAYMENT")
    assert split["min_total"] == 0 and split["window_minutes"] == 0
    assert params_of(TEMPLATES, "HIGH_AMOUNT")["category_thresholds"] == {}
    assert params_of(TEMPLATES, "HIGH_AMOUNT")["enabled"] is True


def test_the_screen_gets_the_kind_of_control_each_parameter_needs():
    info = describe(TEMPLATES, {})
    assert one(info, "HIGH_AMOUNT", "category_thresholds")["kind"] == "map"
    assert one(info, "OFF_HOURS", "holidays")["kind"] == "list"
    assert one(info, "OFF_HOURS", "check_weekend")["kind"] == "switch"
    assert one(info, "SPLIT_PAYMENT", "window_minutes")["kind"] == "number"
    assert one(info, "SPLIT_PAYMENT", "min_total")["kind"] == "number"


def test_a_stored_override_shows_as_the_current_value():
    info = describe(TEMPLATES, {"HIGH_AMOUNT": {"category_thresholds": {"영화관": 100000}}, "OFF_HOURS": {"enabled": False}})
    assert one(info, "HIGH_AMOUNT", "category_thresholds")["value"] == {"영화관": 100000}
    assert one(info, "OFF_HOURS", "enabled")["value"] is False
    assert one(info, "OFF_HOURS", "enabled")["default"] is True


# --- only real changes are stored ---------------------------------------------------------------

from app.anomaly.settings import without_defaults  # noqa: E402


def test_values_equal_to_the_defaults_are_dropped():
    clean = {"HIGH_AMOUNT": {"threshold": 500000, "enabled": True, "category_thresholds": {}},
             "OFF_HOURS": {"night_start": "23", "holidays": []}}
    assert without_defaults(TEMPLATES, clean) == {}


def test_real_changes_are_kept_and_the_rest_dropped():
    clean = {"HIGH_AMOUNT": {"threshold": 300000, "severity": "high"},
             "OFF_HOURS": {"enabled": False, "night_start": "23"}}
    assert without_defaults(TEMPLATES, clean) == {"HIGH_AMOUNT": {"threshold": 300000}, "OFF_HOURS": {"enabled": False}}


def test_a_changed_severity_and_map_are_kept():
    clean = {"HIGH_AMOUNT": {"severity": "low", "category_thresholds": {"영화관": 100000}}}
    assert without_defaults(TEMPLATES, clean) == clean
