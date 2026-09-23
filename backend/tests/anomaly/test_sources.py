import pytest

from app.anomaly.rules import RULES, SOURCES, Source, rules_by_source
from app.services.anomaly_service import build_source_query


def test_every_rule_names_a_source_that_exists():
    for rule in RULES:
        assert rule.source in SOURCES, f"{rule.code} points at unknown source {rule.source}"


def test_all_four_rules_currently_live_on_the_approval_source():
    grouped = rules_by_source(RULES)
    assert set(grouped) == {"approval"}
    assert len(grouped["approval"]) == 4


def test_grouping_keeps_each_rule_under_its_own_source():
    other = Source(key="other", label="다른 원천", view="v_other", date_column="d")
    moved = [
        RULES[0],
        type(RULES[1])(**{**RULES[1].__dict__, "source": "other"}),
    ]
    grouped = rules_by_source(moved)
    assert grouped[RULES[0].source] == [RULES[0]]
    assert grouped["other"][0].code == RULES[1].code
    assert other.view == "v_other"


def test_approval_source_reads_the_view_the_rules_were_written_against():
    approval = SOURCES["approval"]
    assert approval.view == "v_approval"
    assert approval.date_column == "transdate"


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
