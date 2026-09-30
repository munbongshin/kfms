"""Only administrators see SQL; everyone else gets answers.

The screen hides the SQL tab, but a browser's developer tools would still show
the response, so these rules strip it on the server.
"""
import pytest

from app.auth.sql_visibility import (
    BLOCKED,
    FAILED,
    can_see_sql,
    combined_result,
    execution_result,
    history_row,
    report_meta,
    safe_error,
    table_page,
)

SQL = "SELECT cardno FROM card_data"


def ran():
    return {
        "success": True, "results": [{"n": 1}], "row_count": 1, "execution_time_ms": 5,
        "history_id": 9, "warnings": ["no LIMIT"], "sql": SQL,
    }


def deep_contains(value, needle):
    return needle in repr(value)


# --- who ------------------------------------------------------------------------------------

def test_only_an_administrator_sees_sql():
    assert can_see_sql("admin") is True
    for role in ("auditor", "viewer", "", "anything"):
        assert can_see_sql(role) is False


# --- an executed query ------------------------------------------------------------------------

def test_an_administrator_gets_the_full_execution_result():
    assert execution_result(ran(), "admin") == ran()


@pytest.mark.parametrize("role", ["auditor", "viewer"])
def test_others_get_rows_and_timing_but_no_sql_or_warnings(role):
    out = execution_result(ran(), role)
    assert out == {"success": True, "results": [{"n": 1}], "row_count": 1, "execution_time_ms": 5, "history_id": 9}
    assert not deep_contains(out, "SELECT")


def test_a_failed_run_says_only_that_it_failed():
    failed = {"success": False, "error": 'column "x" does not exist LINE 1: SELECT x FROM t', "warnings": ["w"], "history_id": 4}
    out = execution_result(failed, "viewer")
    assert out == {"success": False, "error": FAILED, "history_id": 4}
    assert not deep_contains(out, "SELECT")


def test_an_administrator_still_sees_the_database_error():
    failed = {"success": False, "error": "boom", "history_id": 4}
    assert execution_result(failed, "admin")["error"] == "boom"


# --- generate and execute -----------------------------------------------------------------------

def test_the_generation_block_is_dropped_for_others():
    full = {**ran(), "generation": {"sql": SQL, "llm_provider": "ollama", "validation": {"warnings": ["x"]}}}
    out = combined_result(full, "viewer")
    assert "generation" not in out and not deep_contains(out, "SELECT")
    assert out["results"] == [{"n": 1}]


def test_the_administrator_keeps_the_generation_block():
    full = {**ran(), "generation": {"sql": SQL}}
    assert combined_result(full, "admin")["generation"]["sql"] == SQL


def test_an_unsafe_query_needing_approval_is_simply_blocked_for_others():
    pending = {"success": False, "requires_approval": True, "generation": {"sql": "DELETE FROM t"}, "message": "SQL requires user approval"}
    out = combined_result(pending, "viewer")
    assert out == {"success": False, "error": BLOCKED}
    assert not deep_contains(out, "DELETE")


def test_the_administrator_still_gets_the_approval_request():
    pending = {"success": False, "requires_approval": True, "generation": {"sql": "DELETE FROM t"}}
    assert combined_result(pending, "admin") == pending


# --- errors ---------------------------------------------------------------------------------------

def test_an_error_message_is_generic_for_others_and_whole_for_administrators():
    detail = "Execution failed: syntax error at or near SELECT"
    assert safe_error("viewer", detail) == FAILED
    assert safe_error("auditor", detail) == FAILED
    assert safe_error("admin", detail) == detail


# --- history ------------------------------------------------------------------------------------

def hist():
    return {"id": 1, "question": "q", "generated_sql": SQL, "error_message": "LINE 1: SELECT", "status": "error"}


def test_history_rows_lose_sql_and_raw_errors_for_others():
    out = history_row(hist(), "viewer")
    assert out["generated_sql"] == "" and out["error_message"] == FAILED
    assert out["question"] == "q" and out["status"] == "error"


def test_a_history_row_without_an_error_keeps_no_error():
    row = {**hist(), "error_message": None}
    assert history_row(row, "viewer")["error_message"] is None


def test_history_is_untouched_for_administrators():
    assert history_row(hist(), "admin") == hist()


def test_the_input_row_is_never_modified():
    original = hist()
    history_row(original, "viewer")
    assert original["generated_sql"] == SQL


# --- reports ----------------------------------------------------------------------------------------

def test_report_metadata_hides_the_sql_and_the_raw_error():
    meta = {"id": 1, "name": "n", "sql": SQL, "last_error": "LINE 1: SELECT", "last_status": "error"}
    out = report_meta(meta, "viewer")
    assert out["sql"] == "" and out["last_error"] == FAILED and out["name"] == "n"
    assert report_meta(meta, "admin") == meta


def test_a_report_that_has_not_failed_shows_no_error():
    meta = {"sql": SQL, "last_error": None}
    assert report_meta(meta, "viewer")["last_error"] is None


# --- table preview ------------------------------------------------------------------------------------

def test_the_table_preview_sql_is_removed_for_others():
    page = {"rows": [], "columns": ["a"], "sql": 'SELECT "a" FROM "t"'}
    assert "sql" not in table_page(page, "viewer")
    assert table_page(page, "admin") == page
