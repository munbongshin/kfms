"""Reading a database's tables, views and their descriptions in one pass.

The catalog must cover every schema the connection may read, not only public,
and every kind of relation a question can be asked about — tables, views,
materialized views, foreign tables and partitioned tables (but not their
individual partitions, which would repeat the parent's rows).
"""
from app.db.catalog import (
    SchemaCache,
    build_catalog,
    quote_relation,
    split_key,
    table_key,
)


def row(schema, table, kind, column, *, table_comment=None, column_comment=None, type_="text"):
    return {
        "schema_name": schema,
        "table_name": table,
        "relkind": kind,
        "table_comment": table_comment,
        "column_name": column,
        "data_type": type_,
        "nullable": True,
        "column_default": None,
        "column_comment": column_comment,
    }


ROWS = [
    row("public", "card_data", "r", "cardno", column_comment="카드번호"),
    row("public", "v_approval", "v", "cardno", table_comment="승인내역 테이블"),
    row("public", "v_approval", "v", "appramt", column_comment="공급가액[승인금액,현지금액]"),
    row("cats", "approval_summary", "m", "total", table_comment="승인 집계"),
    row("remote", "partner_sales", "f", "amount"),
]


# --- naming ----------------------------------------------------------------

def test_public_tables_keep_their_bare_name():
    assert table_key("public", "v_approval") == "v_approval"


def test_other_schemas_are_qualified():
    assert table_key("cats", "approval") == "cats.approval"


def test_a_public_name_with_a_dot_is_qualified_so_it_cannot_be_misread():
    assert table_key("public", "a.b") == "public.a.b"
    assert split_key("public.a.b") == ("public", "a.b")


def test_keys_split_back_into_schema_and_name():
    assert split_key("v_approval") == ("public", "v_approval")
    assert split_key("cats.approval") == ("cats", "approval")


def test_a_public_relation_is_quoted_bare():
    assert quote_relation("v_approval") == '"v_approval"'


def test_a_qualified_relation_quotes_both_parts():
    assert quote_relation("cats.approval") == '"cats"."approval"'


def test_quotes_inside_names_are_escaped():
    assert quote_relation('we"ird') == '"we""ird"'


# --- build_catalog ---------------------------------------------------------

def test_every_schema_and_relation_kind_is_kept():
    tables, _ = build_catalog(ROWS)
    assert list(tables) == ["card_data", "v_approval", "cats.approval_summary", "remote.partner_sales"]
    assert tables["cats.approval_summary"]["kind"] == "materialized_view"
    assert tables["remote.partner_sales"]["kind"] == "foreign_table"
    assert tables["v_approval"]["kind"] == "view"


def test_table_descriptions_are_read():
    tables, _ = build_catalog(ROWS)
    assert tables["v_approval"]["comment"] == "승인내역 테이블"
    assert tables["card_data"]["comment"] is None


def test_columns_keep_their_order_and_details():
    _, columns = build_catalog(ROWS)
    assert [c["name"] for c in columns["v_approval"]] == ["cardno", "appramt"]
    assert columns["v_approval"][1]["type"] == "text"


def test_views_borrow_the_comments_of_the_tables_they_read():
    _, columns = build_catalog(ROWS)
    assert columns["v_approval"][0]["comment"] == "카드번호"


def test_the_catalog_carries_comments_only_because_labels_are_managed_data():
    # Display names are laid over a copy per request (see test_column_labels.py),
    # so the cached catalog must not bake any in.
    _, columns = build_catalog(ROWS)
    assert all("label" not in c for cols in columns.values() for c in cols)


def test_an_empty_database_has_no_tables():
    assert build_catalog([]) == ({}, {})


# --- cache -----------------------------------------------------------------

class Clock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now


def test_a_cached_catalog_is_reused_until_it_expires():
    clock = Clock()
    cache = SchemaCache(ttl_seconds=300, clock=clock)
    cache.put("1", "catalog")
    clock.now = 299
    assert cache.get("1") == "catalog"
    clock.now = 301
    assert cache.get("1") is None


def test_invalidating_one_connection_leaves_the_others():
    cache = SchemaCache(ttl_seconds=300, clock=Clock())
    cache.put("1", "a")
    cache.put("2", "b")
    cache.invalidate("1")
    assert cache.get("1") is None
    assert cache.get("2") == "b"


def test_a_kind_that_arrives_as_bytes_is_still_recognised():
    # PostgreSQL's "char" type (relkind) can reach Python as bytes.
    tables, _ = build_catalog([row("public", "v_approval", b"v", "cardno")])
    assert tables["v_approval"]["kind"] == "view"


# --- views built on a table -------------------------------------------------

def dep(source, view, column, source_schema="public", view_schema="public"):
    return {
        "source_schema": source_schema,
        "source_name": source,
        "view_schema": view_schema,
        "view_name": view,
        "column_name": column,
    }


BASE = [
    row("public", "card_data", "r", "source_table"),
    row("public", "card_data", "r", "cardno"),
    row("public", "card_data", "r", "appramt"),
    row("public", "v_approval", "v", "cardno"),
    row("public", "v_approval", "v", "appramt"),
    row("public", "v_bill", "v", "cardno"),
]


def test_a_table_lists_the_views_built_on_it_and_what_they_read():
    deps = [
        dep("card_data", "v_approval", "source_table"),
        dep("card_data", "v_approval", "cardno"),
        dep("card_data", "v_approval", "appramt"),
        dep("card_data", "v_bill", "source_table"),
        dep("card_data", "v_bill", "cardno"),
    ]
    tables, _ = build_catalog(BASE, deps)
    assert tables["card_data"]["derived_views"] == {
        "v_approval": ["source_table", "cardno", "appramt"],
        "v_bill": ["source_table", "cardno"],
    }


def test_columns_read_only_in_a_where_clause_still_count():
    # v_approval filters on source_table without selecting it; PostgreSQL
    # still records the dependency, so coverage is judged on what views read.
    deps = [dep("card_data", "v_approval", c) for c in ("source_table", "cardno", "appramt")]
    tables, _ = build_catalog(BASE, deps)
    assert "source_table" in tables["card_data"]["derived_views"]["v_approval"]


def test_a_table_with_no_views_on_it_has_none():
    tables, _ = build_catalog(BASE, [])
    assert tables["card_data"]["derived_views"] == {}


def test_views_the_connection_cannot_read_are_ignored():
    # Only views in the catalog (readable) can stand in for a table.
    deps = [dep("card_data", "hidden_view", "cardno")]
    tables, _ = build_catalog(BASE, deps)
    assert tables["card_data"]["derived_views"] == {}


def test_views_in_other_schemas_use_their_qualified_name():
    rows = BASE + [row("audit", "v_card", "v", "cardno")]
    deps = [dep("card_data", "v_card", "cardno", view_schema="audit")]
    tables, _ = build_catalog(rows, deps)
    assert tables["card_data"]["derived_views"] == {"audit.v_card": ["cardno"]}


def test_a_column_is_listed_once_per_view():
    deps = [dep("card_data", "v_approval", "cardno"), dep("card_data", "v_approval", "cardno")]
    tables, _ = build_catalog(BASE, deps)
    assert tables["card_data"]["derived_views"]["v_approval"] == ["cardno"]
