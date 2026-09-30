"""The SQL safety check: what is allowed, what is blocked, and that its notes are in Korean."""
import re

import pytest

from app.utils.sql_validator import SQLValidator

check = SQLValidator.validate


def test_a_plain_select_is_safe_and_notes_the_missing_limit():
    out = check("SELECT a FROM t")
    assert out["is_safe"] is True and out["is_read_only"] is True
    assert any("LIMIT" in w for w in out["warnings"])


def test_a_select_with_a_limit_has_no_notes():
    assert check("SELECT a FROM t LIMIT 5")["warnings"] == []


@pytest.mark.parametrize("sql", [
    "DELETE FROM t", "DROP TABLE t", "UPDATE t SET a = 1", "INSERT INTO t VALUES (1)", "TRUNCATE t",
])
def test_anything_that_changes_data_is_blocked(sql):
    out = check(sql)
    assert out["is_safe"] is False and out["is_read_only"] is False and out["warnings"]


def test_an_empty_query_is_not_safe():
    assert check("   ")["is_safe"] is False


def test_a_suspicious_pattern_is_a_note_not_a_block():
    out = check("SELECT a INTO b FROM t")
    assert out["warnings"]  # flagged for the reviewer


def test_every_warning_is_written_in_korean():
    for sql in ("DELETE FROM t", "SELECT a FROM t", "", "SELECT a INTO b FROM t"):
        for warning in check(sql)["warnings"]:
            assert re.search("[가-힣]", warning), warning
