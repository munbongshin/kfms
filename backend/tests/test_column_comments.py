"""Views carry no column comments of their own, so they borrow the table's.

v_approval and the other views are plain SELECTs over card_data. PostgreSQL does
not copy comments onto view columns, so without borrowing, the Korean labels
would show for card_data but vanish the moment a user opens a view.
"""
from app.db.column_display_names import DISPLAY_NAMES
from app.db.connection_pool import add_display_labels, borrow_missing_comments


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


def test_a_short_display_name_replaces_a_long_comment_on_screen():
    # The workbook calls appramt 공급가액[승인금액,현지금액]; users say 승인금액.
    schema = {"v_approval": [col("appramt", "공급가액[승인금액,현지금액]")]}
    add_display_labels(schema)
    assert schema["v_approval"][0]["label"] == "승인금액"


def test_the_full_comment_is_kept_for_the_prompt():
    schema = {"v_approval": [col("appramt", "공급가액[승인금액,현지금액]")]}
    add_display_labels(schema)
    assert schema["v_approval"][0]["comment"] == "공급가액[승인금액,현지금액]"


def test_without_a_display_name_the_comment_is_the_label():
    schema = {"card_data": [col("cardno", "카드번호")]}
    add_display_labels(schema)
    assert schema["card_data"][0]["label"] == "카드번호"


def test_a_column_with_neither_has_no_label():
    schema = {"t": [col("mystery")]}
    add_display_labels(schema)
    assert schema["t"][0]["label"] is None


def test_every_display_name_is_short_and_plain():
    # The point of a display name is to drop the workbook's bracketed notes.
    for name, label in DISPLAY_NAMES.items():
        assert label.strip() == label and label, name
        assert "[" not in label, name


def test_no_display_name_uses_a_term_the_users_do_not_use():
    for name, label in DISPLAY_NAMES.items():
        assert "현지금액" not in label, name


def test_every_column_named_for_local_amount_has_a_display_name():
    # The workbook's 현지금액 must not reach the screen through a raw comment.
    for name in ("appramt", "apprtot", "curracqutot"):
        assert name in DISPLAY_NAMES
