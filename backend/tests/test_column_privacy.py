"""People who are not administrators see Korean column names only.

The server converts what it sends — the schema, table previews, query results,
saved results, anomaly details — so the English column names never reach the
browser, not even in the raw response.
"""
from app.db.column_labels import Override, apply_labels, coverage
from app.db.column_privacy import (
    PLACEHOLDER,
    anonymize_detail,
    has_korean,
    labels_from_sql,
    relabel_rows,
    result_labels,
    visible_schema,
)


def col(name, comment=None):
    return {"name": name, "type": "text", "nullable": True, "default": None, "comment": comment}


TERMS = {"sum": "합계", "count": "건수", "avg": "평균", "max": "최대값", "min": "최소값", "?column?": "계산값"}


# --- what counts as a Korean name ------------------------------------------------------------------

def test_hangul_is_korean_and_ascii_is_not():
    assert has_korean("카드번호") and has_korean("총 매출액 (원)") and has_korean("ID번호")
    assert not has_korean("cardno") and not has_korean("total_amt") and not has_korean("")


def test_a_column_named_in_korean_already_has_its_name():
    # Uploaded spreadsheets keep their Korean headers as column names.
    out = apply_labels({"t": [col("과제명")]}, [])
    assert out["t"][0]["label"] == "과제명" and out["t"][0]["label_source"] == "name"


def test_such_a_column_is_counted_as_mapped_on_the_admin_screen():
    row = coverage({"t": [col("과제명"), col("mystery")]}, [])
    by = {r["name"]: r for r in row}
    assert by["과제명"]["mapped"] is True and by["mystery"]["mapped"] is False


def test_a_comment_still_beats_a_korean_physical_name():
    out = apply_labels({"t": [col("과제명", "연구 과제 이름")]}, [])
    assert out["t"][0]["label"] == "연구 과제 이름"


# --- the schema people see --------------------------------------------------------------------------

def labeled(schema, overrides=()):
    return apply_labels(schema, list(overrides))


def test_the_visible_schema_names_columns_by_their_korean_label():
    schema = labeled({"card_data": [col("cardno", "카드번호"), col("appramt", "공급가액[승인금액,현지금액]")]},
                     [Override(None, "appramt", "승인금액")])
    visible, _ = visible_schema(schema)
    assert [c["name"] for c in visible["card_data"]] == ["카드번호", "승인금액"]
    assert not any(has_korean(c["name"]) is False for c in visible["card_data"])


def test_no_english_name_survives_anywhere_in_the_visible_schema():
    schema = labeled({"t": [col("cardno", "카드번호"), col("secret_col")]})
    text = repr(visible_schema(schema)[0])
    assert "cardno" not in text and "secret_col" not in text


def test_a_column_without_any_korean_name_gets_a_numbered_placeholder():
    schema = labeled({"t": [col("a1"), col("b2"), col("cardno", "카드번호")]})
    names = [c["name"] for c in visible_schema(schema)[0]["t"]]
    assert names == [f"{PLACEHOLDER} 1", f"{PLACEHOLDER} 2", "카드번호"]


def test_an_english_only_comment_is_not_shown_as_a_name():
    schema = labeled({"t": [col("cardno", "Card number")]})
    assert visible_schema(schema)[0]["t"][0]["name"].startswith(PLACEHOLDER)


def test_two_columns_with_one_label_stay_distinguishable():
    schema = labeled({"t": [col("bizno1", "사업자번호"), col("bizno2", "사업자번호")]})
    visible, real = visible_schema(schema)
    assert [c["name"] for c in visible["t"]] == ["사업자번호", "사업자번호 (2)"]
    assert real["t"] == {"사업자번호": "bizno1", "사업자번호 (2)": "bizno2"}


def test_the_server_can_map_a_visible_name_back_to_the_real_column():
    schema = labeled({"t": [col("cardno", "카드번호")]})
    _, real = visible_schema(schema)
    assert real["t"]["카드번호"] == "cardno"


def test_defaults_and_untranslated_comments_are_not_passed_on():
    schema = labeled({"t": [{**col("id", "번호"), "default": "nextval('public.t_id_seq'::regclass)"}, col("x", "Note")]})
    columns = visible_schema(schema)[0]["t"]
    assert columns[0]["default"] is None and columns[0]["comment"] == "번호"
    assert columns[1]["comment"] is None


def test_the_type_and_nullability_are_kept():
    schema = labeled({"t": [{**col("n", "수량"), "type": "integer", "nullable": False}]})
    c = visible_schema(schema)[0]["t"][0]
    assert c["type"] == "integer" and c["nullable"] is False


# --- computed-column names from the SQL ---------------------------------------------------------------

NAMES = {"appramt": "승인금액", "cardno": "카드번호"}


def test_an_aggregate_gets_the_column_name_plus_the_term():
    sql = "SELECT SUM(appramt) AS total_appr_amt FROM v_approval"
    assert labels_from_sql(sql, NAMES, TERMS)["total_appr_amt"] == "승인금액 합계"


def test_an_unaliased_aggregate_uses_the_name_postgres_gives_it():
    assert labels_from_sql("SELECT SUM(appramt) FROM v_approval", NAMES, TERMS)["sum"] == "승인금액 합계"


def test_count_star_is_a_plain_count():
    assert labels_from_sql("SELECT COUNT(*) AS cnt FROM t", NAMES, TERMS)["cnt"] == "건수"


def test_distinct_and_qualified_names_resolve():
    sql = 'SELECT COUNT(DISTINCT a."cardno") AS cards FROM v_approval a'
    assert labels_from_sql(sql, NAMES, TERMS)["cards"] == "카드번호 건수"


def test_an_unquoted_alias_is_folded_to_lower_case_and_a_quoted_one_keeps_its_case():
    assert "maxamt" in labels_from_sql("SELECT MAX(appramt) AS MaxAmt FROM t", NAMES, TERMS)
    assert "MinAmt" in labels_from_sql('SELECT MIN(appramt) AS "MinAmt" FROM t', NAMES, TERMS)


def test_a_korean_alias_is_left_alone():
    assert labels_from_sql('SELECT SUM(appramt) AS "총 매출액" FROM t', NAMES, TERMS) == {}


def test_an_expression_inside_the_aggregate_is_not_guessed_at():
    assert "revenue" not in labels_from_sql("SELECT SUM(price * qty) AS revenue FROM t", NAMES, TERMS)


def test_a_function_without_a_term_is_skipped():
    assert labels_from_sql("SELECT SUM(appramt) AS s FROM t", NAMES, {}) == {}


# --- which name a plain column takes -----------------------------------------------------------------------

def test_the_tables_the_sql_reads_name_a_column_first():
    schema = labeled(
        {"card_data": [col("appramt", "공급가액")], "v_approval": [col("appramt", "승인 공급가액")]},
    )
    assert result_labels(schema, "SELECT appramt FROM v_approval")["appramt"] == "승인 공급가액"
    assert result_labels(schema, "SELECT appramt FROM card_data")["appramt"] == "공급가액"


def test_only_korean_labels_are_offered_for_results():
    schema = labeled({"t": [col("a", "Amount"), col("b", "금액")]})
    labels = result_labels(schema, "SELECT * FROM t")
    assert "a" not in labels and labels["b"] == "금액"


# --- query results ------------------------------------------------------------------------------------------

def test_result_columns_are_renamed_to_korean_and_values_are_kept():
    rows = [{"cardno": "4111", "appramt": 1000}]
    out = relabel_rows(rows, "SELECT cardno, appramt FROM t", NAMES, TERMS)
    assert out == [{"카드번호": "4111", "승인금액": 1000}]


def test_the_column_order_is_kept():
    out = relabel_rows([{"appramt": 1, "cardno": 2}], "SELECT appramt, cardno FROM t", NAMES, TERMS)
    assert list(out[0]) == ["승인금액", "카드번호"]


def test_a_korean_alias_from_the_model_is_kept_as_it_is():
    out = relabel_rows([{"총 승인금액": 5}], 'SELECT SUM(appramt) AS "총 승인금액" FROM t', NAMES, TERMS)
    assert list(out[0]) == ["총 승인금액"]


def test_an_english_alias_on_an_aggregate_gets_its_computed_name():
    out = relabel_rows([{"total_amt": 5}], "SELECT SUM(appramt) AS total_amt FROM t", NAMES, TERMS)
    assert list(out[0]) == ["승인금액 합계"]


def test_an_english_column_with_no_korean_name_never_shows_through():
    out = relabel_rows([{"mystery": 1, "other_x": 2}], "SELECT mystery, other_x FROM t", NAMES, TERMS)
    assert not any(k.isascii() for k in out[0])
    assert len(out[0]) == 2  # both survive, distinguishably


def test_two_columns_with_one_name_are_told_apart():
    names = {"bizno1": "사업자번호", "bizno2": "사업자번호"}
    out = relabel_rows([{"bizno1": "a", "bizno2": "b"}], "SELECT bizno1, bizno2 FROM t", names, TERMS)
    assert out == [{"사업자번호": "a", "사업자번호 (2)": "b"}]


def test_every_row_is_renamed_the_same_way():
    rows = [{"cardno": "1"}, {"cardno": "2"}]
    assert relabel_rows(rows, "SELECT cardno FROM t", NAMES, TERMS) == [{"카드번호": "1"}, {"카드번호": "2"}]


def test_no_rows_is_no_rows():
    assert relabel_rows([], "SELECT 1", NAMES, TERMS) == []


def test_the_input_rows_are_not_modified():
    rows = [{"cardno": "1"}]
    relabel_rows(rows, "SELECT cardno FROM t", NAMES, TERMS)
    assert rows == [{"cardno": "1"}]


def test_a_korean_physical_column_name_is_kept():
    out = relabel_rows([{"과제명": "x"}], "SELECT 과제명 FROM t", {}, TERMS)
    assert list(out[0]) == ["과제명"]


# --- anomaly detail -------------------------------------------------------------------------------------------

def test_detail_fields_are_renamed_and_english_only_ones_become_placeholders():
    detail = {"seq": 7, "core": [{"field": "cardno", "label": "카드번호", "value": "4111"}],
              "rest": [{"field": "merchname", "label": "merchname", "value": "가게"},
                       {"field": "weird_col", "label": "weird_col", "value": 1}]}
    out = anonymize_detail(detail, {"merchname": "가맹점명"})
    assert [i["field"] for i in out["core"]] == ["카드번호"]
    assert [(i["field"], i["label"]) for i in out["rest"]] == [("가맹점명", "가맹점명"), (f"{PLACEHOLDER} 1", f"{PLACEHOLDER} 1")]
    assert "weird_col" not in repr(out) and "merchname" not in repr(out) and "cardno" not in repr(out)


def test_detail_values_and_the_seq_are_untouched():
    detail = {"seq": 7, "core": [{"field": "cardno", "label": "카드번호", "value": "4111"}], "rest": []}
    out = anonymize_detail(detail, {})
    assert out["seq"] == 7 and out["core"][0]["value"] == "4111"


# --- table preview ------------------------------------------------------------------------------------------

from app.db.column_privacy import to_real, translate_page  # noqa: E402

REAL = {"카드번호": "cardno", "승인금액": "appramt"}


def test_shown_names_map_back_to_real_columns():
    assert to_real(["승인금액", "카드번호"], REAL) == ["appramt", "cardno"]


def test_a_name_the_table_does_not_show_is_refused():
    import pytest
    with pytest.raises(ValueError):
        to_real(["cardno"], REAL)  # the English name is not something a non-administrator can use


def test_nothing_selected_is_nothing_selected():
    assert to_real([], REAL) == []


def test_a_page_is_translated_to_shown_names_in_columns_rows_and_order():
    page = {"table": "t", "columns": ["cardno", "appramt"], "selected": ["appramt"], "order_by": "appramt",
            "descending": False, "total": 1, "offset": 0, "limit": 100, "sql": "SELECT ...",
            "rows": [{"cardno": "4111", "appramt": 5}]}
    out = translate_page(page, REAL)
    assert out["columns"] == ["카드번호", "승인금액"] and out["selected"] == ["승인금액"] and out["order_by"] == "승인금액"
    assert out["rows"] == [{"카드번호": "4111", "승인금액": 5}]
    assert "sql" not in out and "cardno" not in repr(out) and "appramt" not in repr(out)
    assert out["total"] == 1 and out["table"] == "t"


def test_a_translated_page_is_not_the_same_object():
    page = {"columns": ["cardno"], "selected": ["cardno"], "order_by": "cardno", "rows": [{"cardno": 1}]}
    translate_page(page, REAL)
    assert page["columns"] == ["cardno"]
