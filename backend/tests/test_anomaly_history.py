"""What changed between two saved settings, in words a reviewer can read."""
from app.anomaly.rules import TEMPLATES
from app.anomaly.settings_history import changes


def texts(before, after):
    return [c["text"] for c in changes(TEMPLATES, before, after)]


def test_nothing_changed_gives_no_entries():
    assert changes(TEMPLATES, {}, {}) == []
    same = {"HIGH_AMOUNT": {"threshold": 300000}}
    assert changes(TEMPLATES, same, same) == []


def test_an_amount_change_reads_from_and_to():
    (c,) = changes(TEMPLATES, {}, {"HIGH_AMOUNT": {"threshold": 300000}})
    assert c["rule"] == "고액 결제" and c["label"] == "기준 금액(원)"
    assert c["text"] == "500,000 → 300,000"


def test_a_change_back_to_the_default_is_still_a_change_from_what_it_was():
    (c,) = changes(TEMPLATES, {"HIGH_AMOUNT": {"threshold": 300000}}, {})
    assert c["text"] == "300,000 → 500,000"


def test_a_switch_reads_on_and_off():
    assert texts({}, {"OFF_HOURS": {"enabled": False}}) == ["켜짐 → 꺼짐"]


def test_a_severity_reads_in_korean():
    assert texts({}, {"OFF_HOURS": {"severity": "high"}}) == ["보통 → 높음"]


def test_hours_read_as_hours():
    assert texts({}, {"OFF_HOURS": {"night_start": "22"}}) == ["23시 → 22시"]


def test_a_list_shows_what_was_added_and_removed():
    after = {"WATCH_MCC": {"watch_mcc": ["영화관", "볼 링 장", "주점"]}}
    (text,) = texts({}, after)
    assert "+주점" in text
    assert "−상품권 전문판매" in text and "−화   원" in text


def test_a_category_table_shows_added_changed_and_removed_rows():
    before = {"HIGH_AMOUNT": {"category_thresholds": {"영화관": 100000, "화원": 50000}}}
    after = {"HIGH_AMOUNT": {"category_thresholds": {"영화관": 150000, "항공사": 2000000}}}
    (text,) = texts(before, after)
    assert "영화관 100,000→150,000원" in text
    assert "+항공사 2,000,000원" in text
    assert "−화원" in text


def test_several_changes_are_listed_each_with_its_rule():
    found = changes(TEMPLATES, {}, {"HIGH_AMOUNT": {"threshold": 300000}, "SPLIT_PAYMENT": {"min_total": 500000}})
    assert [(c["rule"], c["label"]) for c in found] == [("고액 결제", "기준 금액(원)"), ("분할결제 의심", "합계 금액 기준(원)")]
