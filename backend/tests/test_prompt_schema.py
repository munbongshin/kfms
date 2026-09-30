"""What the LLM sees: every table except those excluded from analysis.

There is no hard-coded rule here any more. Whether a union table such as
card_data is worth sending is the user's call on the analysis-targets screen:
it may be the table a user's own views are built on, or the one a question
needs directly. The catalog only *suggests* excluding tables their views fully
cover (see test_catalog.py).
"""
import pytest

from app.services.llm_service import analysis_schema

VIEWS = ["v_approval", "v_acquire", "v_bill", "v_card_info", "v_card_dept"]


def schema(*tables):
    return {t: [{"name": "c"}] for t in tables}


def test_card_data_is_sent_alongside_its_views_unless_excluded():
    out = analysis_schema(schema("card_data", *VIEWS), excluded=[])
    assert "card_data" in out


def test_card_data_can_be_excluded_like_any_table():
    out = analysis_schema(schema("card_data", *VIEWS), excluded=["card_data"])
    assert "card_data" not in out
    assert set(out) == set(VIEWS)


def test_excluded_tables_never_reach_the_llm():
    out = analysis_schema(schema("retail_sales", "v_approval", "excel_1"), excluded=["excel_1"])
    assert set(out) == {"retail_sales", "v_approval"}


def test_nothing_excluded_means_everything():
    s = schema("retail_sales", "v_approval")
    assert analysis_schema(s, excluded=[]) == s


def test_a_stale_exclusion_is_harmless():
    # A table dropped after it was excluded must not break questions.
    s = schema("retail_sales")
    assert analysis_schema(s, excluded=["gone"]) == s


def test_the_input_is_not_modified():
    s = schema("card_data", *VIEWS)
    analysis_schema(s, excluded=["card_data"])
    assert "card_data" in s


def test_excluding_everything_is_refused():
    with pytest.raises(ValueError, match="분석 대상"):
        analysis_schema(schema("retail_sales"), excluded=["retail_sales"])
