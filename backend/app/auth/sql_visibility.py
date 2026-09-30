"""SQL is for administrators; everyone else gets answers.

Hiding the SQL tab on screen is not enough: a browser's developer tools show the
whole response. So the rules live here, on the server, and every response that
could carry SQL passes through one of these functions for the caller's role.

Others also get generic error text, because a database error quotes the SQL
("LINE 1: SELECT ...") and would leak it the same way.
"""
from typing import Any, Dict, Mapping

FAILED = "질문을 처리하지 못했습니다. 질문을 바꿔 다시 시도하거나 관리자에게 문의하세요."
BLOCKED = "이 질문으로는 조회할 수 없는 내용이 만들어졌습니다. 질문을 바꿔 다시 시도해 보세요."

_RESULT_KEYS = ("success", "results", "row_count", "execution_time_ms", "history_id")


def can_see_sql(role: str) -> bool:
    return role == "admin"


def safe_error(role: str, message: str) -> str:
    """The message as the role may read it."""
    return message if can_see_sql(role) else FAILED


def execution_result(result: Mapping[str, Any], role: str) -> Dict[str, Any]:
    """An executed query as the role may see it: rows and timing, never SQL."""
    if can_see_sql(role):
        return dict(result)
    out = {k: result[k] for k in _RESULT_KEYS if k in result}
    if not result.get("success"):
        out["error"] = FAILED
    return out


def combined_result(result: Mapping[str, Any], role: str) -> Dict[str, Any]:
    """The result of generate-and-execute. Someone who cannot read SQL cannot
    approve it either, so a query that needs approval is simply refused."""
    if can_see_sql(role):
        return dict(result)
    if result.get("requires_approval"):
        return {"success": False, "error": BLOCKED}
    return execution_result(result, role)


def history_row(row: Mapping[str, Any], role: str) -> Dict[str, Any]:
    out = dict(row)
    if not can_see_sql(role):
        out["generated_sql"] = ""
        if out.get("error_message"):
            out["error_message"] = FAILED
    return out


def report_meta(meta: Mapping[str, Any], role: str) -> Dict[str, Any]:
    out = dict(meta)
    if not can_see_sql(role):
        out["sql"] = ""
        if out.get("last_error"):
            out["last_error"] = FAILED
    return out


def table_page(page: Mapping[str, Any], role: str) -> Dict[str, Any]:
    out = dict(page)
    if not can_see_sql(role):
        out.pop("sql", None)
    return out
