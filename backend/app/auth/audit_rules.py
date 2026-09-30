"""Which requests go in the audit log.

Every change, and every read that shows card numbers or saved results. Routine
reads (lists, settings pages) would only bury the entries that matter.
"""
import re

API_PREFIX = "/api/v1"

# Calls that record their own richer entry (the SQL run, who logged in), so the
# generic log skips them instead of writing a second, poorer line.
SELF_LOGGED_POST = ("/query/execute", "/query/generate-and-execute", "/auth/login", "/auth/setup")
_ROWS = re.compile(r"/databases/[^/]+/tables/[^/]+/rows")
_HISTORY_ONE = re.compile(r"/(history|reports)/\d+")
# Changes that are really checks or drafts.
_NOISE = re.compile(r"/query/(validate|generate)|/llm-settings/(test|models)|/databases/[^/]+/test")


def _normal(path: str) -> str:
    path = path.split("?")[0]
    return path[len(API_PREFIX):] if path.startswith(API_PREFIX) else path


def is_audited(method: str, path: str, generic: bool = False) -> bool:
    p = _normal(path)
    if generic and (p in SELF_LOGGED_POST or _ROWS.fullmatch(p)):
        return False
    if method in ("GET", "HEAD"):
        return p.endswith("/findings/transactions") or bool(_ROWS.fullmatch(p)) or bool(_HISTORY_ONE.fullmatch(p))
    return not _NOISE.fullmatch(p)
