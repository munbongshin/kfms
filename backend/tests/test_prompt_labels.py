"""The SQL prompt has to carry the Korean business names.

Users ask in Korean ("카테고리별 총 매출액"), and results are read in Korean, so
the model needs each column's business name to pick columns, and a rule to
give computed columns a Korean alias instead of PostgreSQL's bare "sum".
"""
from app.llm.base import SQL_RULES, BaseLLMProvider


def format_schema(schema):
    # format_schema_context uses no instance state; skip the abstract class.
    return BaseLLMProvider.format_schema_context(None, schema)


def col(name, comment=None):
    return {"name": name, "type": "numeric", "nullable": True, "default": None, "comment": comment}


def test_a_columns_business_name_reaches_the_prompt():
    text = format_schema({"retail_sales": [col("total_amount", "매출액")]})
    assert "total_amount" in text
    assert "매출액" in text


def test_the_prompt_prefers_the_display_name():
    # Otherwise the model copies 현지금액 into its aliases.
    column = col("apprtot", "승인합계[현지금액]")
    column["label"] = "승인합계"
    text = format_schema({"v_approval": [column]})
    assert "승인합계" in text
    assert "현지금액" not in text


def test_a_column_without_a_comment_is_listed_plainly():
    text = format_schema({"t": [col("mystery")]})
    line = [l for l in text.splitlines() if "mystery" in l][0]
    assert "--" not in line


def test_the_rules_ask_for_korean_aliases_on_computed_columns():
    assert "alias" in SQL_RULES.lower()
    assert "합계" in SQL_RULES


def test_the_rules_keep_the_read_only_guard():
    assert "SELECT" in SQL_RULES
