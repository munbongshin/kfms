"""Whether two query results are the same answer.

Column names, column order and row order are the SQL writer's choice, so they
are ignored: each row is reduced to its sorted, normalised values and the rows
are compared as a multiset.
"""
from collections import Counter
from datetime import date, datetime
from decimal import Decimal
from typing import Any, List, Mapping, Tuple

_PLACES = 4


def normalize(value: Any) -> str:
    """One comparable form per value: numbers by value, dates as ISO text."""
    if value is None:
        return "∅"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float, Decimal)):
        rounded = round(Decimal(str(value)), _PLACES)
        text = format(rounded.normalize(), "f")
        return text if "." not in text else text.rstrip("0").rstrip(".")
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return str(value).strip()


def _row(row: Mapping[str, Any]) -> Tuple[str, ...]:
    return tuple(sorted(normalize(v) for v in row.values()))


def results_match(expected: List[Mapping[str, Any]], actual: List[Mapping[str, Any]]) -> Tuple[bool, str]:
    """(same answer?, why not)."""
    if len(expected) != len(actual):
        return False, f"행 수가 다릅니다 (정답 {len(expected)}행, 생성 {len(actual)}행)"
    if not expected:
        return True, ""

    if len(expected[0]) != len(actual[0]):
        return False, f"열 수가 다릅니다 (정답 {len(expected[0])}열, 생성 {len(actual[0])}열)"

    if Counter(_row(r) for r in expected) != Counter(_row(r) for r in actual):
        return False, "값이 다릅니다"
    return True, ""
