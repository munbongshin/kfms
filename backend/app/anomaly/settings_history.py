"""What changed between two saved sets of anomaly settings, in words.

Each change lists the rule, the setting, and how it moved — enough for a reviewer
to see later why yesterday's findings differ from today's, and to decide whether
to restore the earlier values.
"""
from typing import Any, Dict, List

from app.anomaly.settings import SEVERITIES, describe

_SEVERITY_NAMES = dict(SEVERITIES)


def _one(unit: str, value: Any) -> str:
    """A single value as it reads on the screen."""
    if unit == "bool":
        return "켜짐" if value else "꺼짐"
    if unit == "severity":
        return _SEVERITY_NAMES.get(value, str(value))
    if unit == "hour":
        return f"{int(value)}시"
    if unit == "count":
        return f"{int(value)}건"
    if unit == "minutes":
        return "하루 전체" if not value else f"{int(value)}분"
    if unit == "amount0":
        return "사용 안 함" if not value else f"{int(value):,}"
    return f"{int(value):,}" if isinstance(value, (int, float)) and not isinstance(value, bool) else str(value)


def _list_text(before: List[str], after: List[str]) -> str:
    added = [f"+{x}" for x in after if x not in before]
    removed = [f"−{x}" for x in before if x not in after]
    return " ".join(added + removed)


def _map_text(before: Dict[str, int], after: Dict[str, int]) -> str:
    parts = []
    for name, amount in after.items():
        if name not in before:
            parts.append(f"+{name} {amount:,}원")
        elif before[name] != amount:
            parts.append(f"{name} {before[name]:,}→{amount:,}원")
    parts += [f"−{name}" for name in before if name not in after]
    return ", ".join(parts)


def _text(unit: str, control: str, before: Any, after: Any) -> str:
    if control == "list":
        return _list_text(list(before or []), list(after or []))
    if control == "map":
        return _map_text(dict(before or {}), dict(after or {}))
    return f"{_one(unit, before)} → {_one(unit, after)}"


def changes(templates, before: Dict[str, Dict[str, Any]], after: Dict[str, Dict[str, Any]]) -> List[Dict[str, Any]]:
    """The settings whose effective value differs between `before` and `after`.

    Compared as effective values, so switching a setting back to its default
    counts as a change from whatever it was.
    """
    was = {r["template"]: {p["key"]: p for p in r["params"]} for r in describe(templates, before)}
    now = describe(templates, after)

    out: List[Dict[str, Any]] = []
    for rule in now:
        for param in rule["params"]:
            old = was[rule["template"]][param["key"]]["value"]
            new = param["value"]
            if old == new:
                continue
            out.append({
                "template": rule["template"],
                "rule": rule["label"],
                "key": param["key"],
                "label": param["label"],
                "before": old,
                "after": new,
                "text": _text(param["unit"], param["kind"], old, new),
            })
    return out
