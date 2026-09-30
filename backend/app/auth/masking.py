"""Hiding card numbers from people who may not see them.

Viewers can ask questions but not read card numbers. Masking goes by the shape
of the value, not only the column name, so `SELECT cardno AS x` does not slip
past it. It is a guard for ordinary use, not a substitute for database-level
permissions: a viewer determined to reassemble a number from pieces (substr)
is a matter for column privileges on the database.
"""
import re
from typing import Any, Dict, List, Mapping

FULL_MASK_COLUMNS = {"registno"}
FULL_ACCESS_ROLES = {"admin", "auditor"}
_CARD_LIKE = re.compile(r"\d{13,19}")


def _mask_digits(match: "re.Match") -> str:
    digits = match.group(0)
    return digits[:4] + "*" * (len(digits) - 8) + digits[-4:]


def mask_value(column: str, value: Any) -> Any:
    if not isinstance(value, str):
        return value
    if column.lower() in FULL_MASK_COLUMNS:
        return "*" * len(value)
    return _CARD_LIKE.sub(_mask_digits, value)


def mask_results(rows: List[Mapping[str, Any]], role: str) -> List[Dict[str, Any]]:
    """Rows as `role` may see them; the input is never modified."""
    if role in FULL_ACCESS_ROLES:
        return list(rows)
    return [{k: mask_value(k, v) for k, v in row.items()} for row in rows]
