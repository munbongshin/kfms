"""Views carry no column comments of their own, so they borrow the table's.

v_approval and the other views are plain SELECTs over card_data. PostgreSQL does
not copy comments onto view columns, so without borrowing, the Korean labels
would show for card_data but vanish the moment a user opens a view.

How a label is chosen on top of the comment is tested in test_column_labels.py.
"""
from app.db.connection_pool import borrow_missing_comments


def col(name, comment=None):
    return {"name": name, "type": "text", "nullable": True, "default": None, "comment": comment}


def test_a_view_column_takes_the_tables_comment():
    schema = {
        "card_data": [col("cardno", "카드번호")],
        "v_approval": [col("cardno")],
    }
    borrow_missing_comments(schema)
    assert schema["v_approval"][0]["comment"] == "카드번호"


def test_a_columns_own_comment_is_not_overwritten():
    schema = {
        "card_data": [col("status", "처리상태")],
        "other": [col("status", "주문상태")],
    }
    borrow_missing_comments(schema)
    assert schema["other"][0]["comment"] == "주문상태"


def test_a_name_no_table_comments_stays_without_one():
    schema = {"v_approval": [col("mystery")]}
    borrow_missing_comments(schema)
    assert schema["v_approval"][0]["comment"] is None


def test_a_blank_comment_counts_as_missing():
    # COMMENT ON ... IS '' would otherwise render an empty header.
    schema = {
        "card_data": [col("cardno", "카드번호")],
        "v_approval": [col("cardno", "  ")],
    }
    borrow_missing_comments(schema)
    assert schema["v_approval"][0]["comment"] == "카드번호"
