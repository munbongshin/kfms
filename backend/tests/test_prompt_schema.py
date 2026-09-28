"""What the LLM sees: every table, except a union table its views already cover.

card_data is the five source tables stacked into one (157 columns); the views
v_approval, v_acquire, v_bill, v_card_info and v_card_dept each select one
source from it and together expose every column. Sending card_data as well
adds 37% to every prompt and answers nothing the views cannot — measured on
gemma4:31b, the same SQL came back without it, about 2 seconds sooner.
"""
from app.services.llm_service import prompt_schema

VIEWS = ["v_approval", "v_acquire", "v_bill", "v_card_info", "v_card_dept"]


def schema(*tables):
    return {t: [{"name": "c"}] for t in tables}


def test_card_data_is_left_out_when_its_views_are_there():
    out = prompt_schema(schema("card_data", "retail_sales", *VIEWS))
    assert "card_data" not in out
    assert set(out) == {"retail_sales", *VIEWS}


def test_card_data_stays_when_a_view_is_missing():
    # Without every view, some source is reachable only through card_data.
    out = prompt_schema(schema("card_data", *VIEWS[:-1]))
    assert "card_data" in out


def test_other_tables_are_untouched():
    s = schema("retail_sales", "excel_upload_1")
    assert prompt_schema(s) == s


def test_the_input_is_not_modified():
    s = schema("card_data", *VIEWS)
    prompt_schema(s)
    assert "card_data" in s
