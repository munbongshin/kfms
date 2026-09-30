"""Column display names are data an administrator manages, not code.

A label resolves in this order: the table's own override, then the connection's
override for that column name, then the column's DB comment. Nothing else.
"""
from app.db.column_labels import (
    DEFAULT_EXPRESSION_TERMS,
    Override,
    apply_labels,
    coverage,
    merge_expression_terms,
    parse_label_sheet,
)


def col(name, comment=None):
    return {"name": name, "type": "text", "nullable": True, "default": None, "comment": comment}


def schema():
    return {
        "card_data": [col("appramt", "공급가액[승인금액,현지금액]"), col("cardno", "카드번호")],
        "v_approval": [col("appramt", "공급가액[승인금액,현지금액]"), col("mystery")],
    }


def label_of(result, table, name):
    return next(c for c in result[table] if c["name"] == name)


# --- resolution --------------------------------------------------------------------------

def test_without_overrides_the_comment_is_the_label():
    out = apply_labels(schema(), [])
    assert label_of(out, "card_data", "cardno")["label"] == "카드번호"
    assert label_of(out, "card_data", "cardno")["label_source"] == "comment"


def test_a_column_with_neither_override_nor_comment_has_no_label():
    c = label_of(apply_labels(schema(), []), "v_approval", "mystery")
    assert c["label"] is None and c["label_source"] is None


def test_a_connection_wide_override_beats_the_comment_in_every_table():
    out = apply_labels(schema(), [Override(None, "appramt", "승인금액")])
    for table in ("card_data", "v_approval"):
        c = label_of(out, table, "appramt")
        assert c["label"] == "승인금액" and c["label_source"] == "connection"


def test_a_table_override_beats_the_connection_wide_one_only_there():
    out = apply_labels(schema(), [
        Override(None, "appramt", "승인금액"),
        Override("v_approval", "appramt", "승인 공급가액"),
    ])
    assert label_of(out, "v_approval", "appramt")["label"] == "승인 공급가액"
    assert label_of(out, "v_approval", "appramt")["label_source"] == "table"
    assert label_of(out, "card_data", "appramt")["label"] == "승인금액"


def test_the_full_comment_is_kept_for_tooltips_and_the_prompt():
    out = apply_labels(schema(), [Override(None, "appramt", "승인금액")])
    assert label_of(out, "card_data", "appramt")["comment"] == "공급가액[승인금액,현지금액]"


def test_a_blank_override_is_ignored():
    out = apply_labels(schema(), [Override(None, "cardno", "   ")])
    assert label_of(out, "card_data", "cardno")["label"] == "카드번호"


def test_applying_labels_leaves_the_cached_schema_untouched():
    original = schema()
    apply_labels(original, [Override(None, "appramt", "승인금액")])
    assert "label" not in original["card_data"][0]


# --- coverage -----------------------------------------------------------------------------

def test_coverage_lists_each_column_name_once_with_its_tables():
    rows = {r["name"]: r for r in coverage(schema(), [])}
    assert rows["appramt"]["tables"] == ["card_data", "v_approval"]
    assert len(rows) == 3


def test_coverage_counts_a_comment_as_mapped_and_a_bare_column_as_unmapped():
    rows = {r["name"]: r for r in coverage(schema(), [])}
    assert rows["cardno"]["mapped"] is True
    assert rows["mystery"]["mapped"] is False


def test_coverage_reports_the_effective_label_and_where_it_came_from():
    rows = {r["name"]: r for r in coverage(schema(), [Override(None, "appramt", "승인금액")])}
    assert rows["appramt"]["label"] == "승인금액" and rows["appramt"]["source"] == "connection"
    assert rows["appramt"]["default_label"] == "공급가액[승인금액,현지금액]"
    assert rows["cardno"]["source"] == "comment"


def test_coverage_carries_table_exceptions():
    rows = {r["name"]: r for r in coverage(schema(), [Override("v_approval", "appramt", "승인 공급가액", 7)])}
    assert rows["appramt"]["exceptions"] == [{"id": 7, "table_key": "v_approval", "label": "승인 공급가액"}]


def test_an_override_for_a_column_that_no_longer_exists_is_reported_not_dropped():
    out = coverage(schema(), [Override(None, "dropped_col", "사라진 컬럼", 3)])
    orphan = next(r for r in out if r["name"] == "dropped_col")
    assert orphan["tables"] == [] and orphan["label"] == "사라진 컬럼"


# --- computed-column terms ------------------------------------------------------------------

def test_terms_default_when_nothing_is_stored():
    terms = {t["func"]: t for t in merge_expression_terms({})}
    assert terms["sum"]["label"] == DEFAULT_EXPRESSION_TERMS["sum"]
    assert terms["sum"]["customized"] is False


def test_a_stored_term_overrides_its_default_and_is_marked():
    terms = {t["func"]: t for t in merge_expression_terms({"sum": "총액"})}
    assert terms["sum"]["label"] == "총액" and terms["sum"]["customized"] is True
    assert terms["sum"]["default"] == DEFAULT_EXPRESSION_TERMS["sum"]
    assert terms["count"]["customized"] is False


# --- reading a sheet of names ---------------------------------------------------------------

def test_a_sheet_with_column_and_korean_name_headers_is_read():
    items, problems = parse_label_sheet([
        ["컬럼명", "한글명"],
        ["appramt", "승인금액"],
        ["cardno", "카드번호"],
    ])
    assert [(i.table_key, i.column_name, i.label) for i in items] == [
        (None, "appramt", "승인금액"), (None, "cardno", "카드번호")]
    assert problems == []


def test_headers_may_be_english_and_in_any_order_with_a_table_column():
    items, _ = parse_label_sheet([
        ["Label", "Table", "Column"],
        ["승인금액", "v_approval", "appramt"],
    ])
    assert (items[0].table_key, items[0].column_name, items[0].label) == ("v_approval", "appramt", "승인금액")


def test_a_label_without_a_column_name_is_reported_by_row_number():
    items, problems = parse_label_sheet([
        ["column", "label"],
        ["appramt", "승인금액"],
        ["", "이름만 있음"],
    ])
    assert len(items) == 1
    assert [p["row"] for p in problems] == [3]


def test_a_name_not_filled_in_yet_is_skipped_quietly():
    # An export lists every unmapped column with a blank label to fill in.
    items, problems = parse_label_sheet([["column", "label"], ["appramt", "승인금액"], ["cardno", ""]])
    assert len(items) == 1 and problems == []


def test_a_sheet_without_the_two_columns_is_refused_with_a_reason():
    items, problems = parse_label_sheet([["foo", "bar"], ["a", "b"]])
    assert items == [] and "헤더" in problems[0]["reason"]


def test_a_repeated_column_keeps_the_last_label():
    items, _ = parse_label_sheet([["column", "label"], ["appramt", "승인금액"], ["appramt", "승인 공급가액"]])
    assert [(i.column_name, i.label) for i in items] == [("appramt", "승인 공급가액")]
