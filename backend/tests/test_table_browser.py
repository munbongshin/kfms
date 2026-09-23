import pytest

from app.services.table_browser import (
    MAX_PAGE_SIZE,
    build_count_query,
    build_rows_query,
    quote,
)

COLUMNS = ["seq", "cardno", "merchname", "apprtot"]
SCHEMA = {"v_approval": COLUMNS, "empty": [], 'we"ird': ['a"b']}


def test_selecting_no_columns_returns_them_all():
    sql, params = build_rows_query(SCHEMA, "v_approval", [], None, False, 100, 0)
    assert sql.startswith('SELECT * FROM')


def test_selected_columns_keep_the_tables_own_order():
    # Checkbox order must not decide column order, or the same selection
    # renders differently depending on which box was ticked first.
    sql, _ = build_rows_query(SCHEMA, "v_approval", ["merchname", "seq"], None, False, 100, 0)
    assert '"seq", "merchname"' in sql


def test_identifiers_are_quoted():
    sql, _ = build_rows_query(SCHEMA, "v_approval", ["seq"], None, False, 100, 0)
    assert 'FROM "v_approval"' in sql


def test_paging_is_ordered_so_pages_cannot_overlap():
    # PostgreSQL does not promise row order without ORDER BY, so an unordered
    # LIMIT/OFFSET can repeat rows on page 2 that already appeared on page 1.
    sql, _ = build_rows_query(SCHEMA, "v_approval", [], None, False, 100, 0)
    assert 'ORDER BY "seq" ASC' in sql


def test_order_defaults_to_the_first_column():
    sql, _ = build_rows_query(SCHEMA, "v_approval", ["merchname"], None, False, 100, 0)
    assert 'ORDER BY "seq" ASC' in sql


def test_order_can_be_chosen_and_reversed():
    sql, _ = build_rows_query(SCHEMA, "v_approval", [], "apprtot", True, 100, 0)
    assert 'ORDER BY "apprtot" DESC' in sql


def test_every_other_column_breaks_ties():
    # Ordering on one column is not a total order: card_data's first column
    # repeats across hundreds of rows, and equal keys let LIMIT/OFFSET hand the
    # same row to two pages. The remaining columns make the sort deterministic.
    sql, _ = build_rows_query(SCHEMA, "v_approval", [], "cardno", False, 100, 0)
    order = sql[sql.index("ORDER BY"):sql.index("LIMIT")]
    assert order.startswith('ORDER BY "cardno" ASC')
    for column in COLUMNS:
        assert quote(column) in order


def test_the_sort_column_is_not_repeated_among_the_tiebreakers():
    sql, _ = build_rows_query(SCHEMA, "v_approval", [], "cardno", False, 100, 0)
    order = sql[sql.index("ORDER BY"):sql.index("LIMIT")]
    assert order.count(quote("cardno")) == 1


def test_tiebreakers_cover_columns_the_caller_did_not_select():
    # Selecting two columns must not narrow the sort to those two, or rows that
    # match on both would still be orderable in any sequence.
    sql, _ = build_rows_query(SCHEMA, "v_approval", ["seq", "cardno"], None, False, 100, 0)
    order = sql[sql.index("ORDER BY"):sql.index("LIMIT")]
    assert quote("merchname") in order
    assert quote("apprtot") in order


def test_limit_and_offset_are_bound_parameters():
    sql, params = build_rows_query(SCHEMA, "v_approval", [], None, False, 50, 200)
    assert "LIMIT :limit OFFSET :offset" in sql
    assert params == {"limit": 50, "offset": 200}


def test_unknown_table_is_refused():
    with pytest.raises(ValueError, match="table"):
        build_rows_query(SCHEMA, "no_such_table; DROP TABLE x", [], None, False, 100, 0)


def test_unknown_column_is_refused():
    with pytest.raises(ValueError, match="column"):
        build_rows_query(SCHEMA, "v_approval", ["cardno; DROP TABLE x"], None, False, 100, 0)


def test_unknown_order_column_is_refused():
    with pytest.raises(ValueError, match="order"):
        build_rows_query(SCHEMA, "v_approval", [], "1; DROP TABLE x", False, 100, 0)


def test_page_size_is_capped():
    with pytest.raises(ValueError, match="limit"):
        build_rows_query(SCHEMA, "v_approval", [], None, False, MAX_PAGE_SIZE + 1, 0)


def test_negative_offset_is_refused():
    with pytest.raises(ValueError, match="offset"):
        build_rows_query(SCHEMA, "v_approval", [], None, False, 100, -1)


def test_a_table_with_no_columns_is_refused():
    with pytest.raises(ValueError, match="column"):
        build_rows_query(SCHEMA, "empty", [], None, False, 100, 0)


def test_count_query_names_the_same_table():
    sql = build_count_query(SCHEMA, "v_approval")
    assert sql == 'SELECT COUNT(*) AS total FROM "v_approval"'


def test_count_query_refuses_an_unknown_table():
    with pytest.raises(ValueError, match="table"):
        build_count_query(SCHEMA, "nope; DROP TABLE x")


def test_a_quote_in_an_identifier_cannot_break_out():
    # The name is validated against the real schema, so this only arrives if a
    # column genuinely contains a quote; it must still be escaped, not injected.
    sql, _ = build_rows_query(SCHEMA, 'we"ird', [], None, False, 10, 0)
    assert 'FROM "we""ird"' in sql
    assert '"a""b"' in sql


def test_selecting_everything_uses_a_star_so_the_query_stays_readable():
    # 157 column names in the projection makes the SQL tab unreadable, and the
    # meaning is the same.
    sql, _ = build_rows_query(SCHEMA, "v_approval", [], None, False, 100, 0)
    assert sql.startswith('SELECT * FROM "v_approval"')


def test_naming_a_subset_still_lists_the_columns():
    sql, _ = build_rows_query(SCHEMA, "v_approval", ["seq", "cardno"], None, False, 100, 0)
    assert 'SELECT "seq", "cardno" FROM' in sql
