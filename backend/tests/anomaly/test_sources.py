import pytest

from app.anomaly.rules import DATE, RULES, SOURCES, Source, rules_by_source
from app.services.anomaly_service import build_source_query


def test_every_rule_names_a_source_that_exists():
    for rule in RULES:
        assert rule.source in SOURCES, f"{rule.code} points at unknown source {rule.source}"


def test_each_source_offers_only_the_rules_its_columns_support():
    grouped = rules_by_source(RULES)
    assert set(grouped) == {"approval", "acquire", "bill"}
    # 승인내역 carries every logical column, so all four templates bind.
    assert len(grouped["approval"]) == 4
    assert len(grouped["acquire"]) == 4
    # 청구내역 has no transaction time, merchant number or category.
    assert [r.code for r in grouped["bill"]] == ["BILL_HIGH_AMOUNT"]


def test_rule_codes_are_unique_so_review_keys_cannot_collide():
    codes = [r.code for r in RULES]
    assert len(codes) == len(set(codes))


def test_a_sources_rules_all_carry_its_prefix():
    for rule in RULES:
        assert rule.code.startswith(SOURCES[rule.source].code_prefix)


def test_approval_rule_codes_stay_bare_so_stored_reviews_keep_matching():
    approval_codes = {r.code for r in RULES if r.source == "approval"}
    assert approval_codes == {"HIGH_AMOUNT", "OFF_HOURS", "WATCH_MCC", "SPLIT_PAYMENT"}


def test_each_source_maps_its_own_physical_date_column():
    assert SOURCES["approval"].columns[DATE] == "transdate"
    assert SOURCES["acquire"].columns[DATE] == "apprdate"
    assert SOURCES["bill"].columns[DATE] == "orgnapprdate"


def test_query_without_a_period_selects_everything():
    sql, params = build_source_query(SOURCES["approval"], None, None)
    assert sql == "SELECT * FROM v_approval"
    assert params == {}


def test_query_with_both_bounds_filters_on_the_source_date_column():
    sql, params = build_source_query(SOURCES["approval"], "2023-06-01", "2023-06-30")
    assert "WHERE transdate >= :date_from AND transdate <= :date_to" in sql
    assert params == {"date_from": "2023-06-01", "date_to": "2023-06-30"}


def test_query_accepts_an_open_ended_period():
    sql, params = build_source_query(SOURCES["approval"], "2023-07-01", None)
    assert "transdate >= :date_from" in sql
    assert "date_to" not in sql
    assert params == {"date_from": "2023-07-01"}

    sql, params = build_source_query(SOURCES["approval"], None, "2023-07-01")
    assert "transdate <= :date_to" in sql
    assert "date_from" not in sql
    assert params == {"date_to": "2023-07-01"}


def test_query_rejects_a_date_that_is_not_iso():
    # The bound is interpolated as a bind parameter, but the column name is not —
    # a malformed date still means a caller bug worth failing loudly on.
    with pytest.raises(ValueError):
        build_source_query(SOURCES["approval"], "2023/06/01", None)


def test_query_rejects_an_inverted_period():
    with pytest.raises(ValueError):
        build_source_query(SOURCES["approval"], "2023-07-31", "2023-06-01")
