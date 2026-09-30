"""Editable anomaly thresholds.

The rules' logic stays in code; only these numbers and lists can be changed
from the screen. Everything is validated before it is stored — an empty list or
a zero amount would quietly switch a rule off.
"""
from dataclasses import replace
from decimal import Decimal
from typing import Any, Dict, List, Tuple

MAX_AMOUNT = 10 ** 12
MAX_LIST = 200

# template -> parameter -> (kind, label, hint)
EDITABLE: Dict[str, Dict[str, Tuple[str, str, str]]] = {
    "HIGH_AMOUNT": {
        "threshold": ("number", "기준 금액(원)", "한 건이 이 금액 이상이면 고액 결제"),
    },
    "OFF_HOURS": {
        "night_start": ("hour", "심야 시작(시)", "이 시각부터 심야 (0~23)"),
        "night_end": ("hour", "심야 종료(시)", "이 시각 전까지 심야 (0~23)"),
    },
    "WATCH_MCC": {
        "watch_mcc": ("list", "주의 업종", "업종명을 한 줄에 하나씩"),
    },
    "SPLIT_PAYMENT": {
        "min_count": ("count", "최소 건수", "같은 카드·가맹점·날짜에 이 건수 이상이면 분할결제 의심"),
        "exclude_merchbizno": ("list", "제외 사업자번호", "분할결제로 보지 않을 가맹점 사업자번호"),
    },
}


def _int(value: Any) -> int:
    if isinstance(value, bool):
        raise ValueError
    return int(str(value).strip())


def _clean_list(value: Any) -> List[str]:
    if not isinstance(value, (list, tuple)):
        raise ValueError
    seen: List[str] = []
    for item in value:
        text = str(item).strip()
        if text and text not in seen:
            seen.append(text)
    return seen


def validate(raw: Dict[str, Dict[str, Any]]) -> Tuple[Dict[str, Dict[str, Any]], List[str]]:
    """(clean overrides, problems). Nothing is stored unless there are none."""
    clean: Dict[str, Dict[str, Any]] = {}
    errors: List[str] = []

    for template, params in (raw or {}).items():
        spec = EDITABLE.get(template)
        if spec is None:
            errors.append(f"알 수 없는 규칙입니다: {template}")
            continue
        for key, value in (params or {}).items():
            if key not in spec:
                errors.append(f"{template}에서 바꿀 수 없는 항목입니다: {key}")
                continue
            kind, label, _ = spec[key]
            try:
                if kind == "number":
                    n = _int(value)
                    if not 1 <= n <= MAX_AMOUNT:
                        raise ValueError
                    parsed: Any = n
                elif kind == "hour":
                    h = _int(value)
                    if not 0 <= h <= 23:
                        raise ValueError
                    parsed = f"{h:02d}"
                elif kind == "count":
                    c = _int(value)
                    if not 2 <= c <= 50:
                        raise ValueError
                    parsed = c
                else:
                    items = _clean_list(value)
                    # An empty list would quietly turn the rule off.
                    if key == "watch_mcc" and not items:
                        raise ValueError
                    if len(items) > MAX_LIST:
                        raise ValueError
                    parsed = items
            except (ValueError, TypeError):
                errors.append(f"{label} 값이 올바르지 않습니다")
                continue
            clean.setdefault(template, {})[key] = parsed

    return clean, errors


def apply_overrides(templates, overrides: Dict[str, Dict[str, Any]]):
    """New templates with the overrides merged in; the originals are untouched."""
    out = []
    for tpl in templates:
        changes = overrides.get(tpl.template)
        if not changes:
            out.append(tpl)
            continue
        params = dict(tpl.params)
        for key, value in changes.items():
            params[key] = Decimal(str(value)) if key == "threshold" else value
        out.append(replace(tpl, params=params))
    return out


def describe(templates, overrides: Dict[str, Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Every editable parameter with its current value and its default."""
    info = []
    for tpl in templates:
        spec = EDITABLE.get(tpl.template)
        if not spec:
            continue
        params = []
        for key, (kind, label, hint) in spec.items():
            default = tpl.params.get(key)
            if isinstance(default, Decimal):
                default = int(default)
            elif kind == "hour":
                default = int(default)
            value = (overrides.get(tpl.template) or {}).get(key, default)
            if kind == "hour":
                value = int(value)
            params.append({
                "key": key,
                "label": label,
                "hint": hint,
                "kind": "number" if kind in ("number", "count", "hour") else "list",
                "unit": kind,
                "value": value,
                "default": default,
            })
        info.append({"template": tpl.template, "label": tpl.label, "severity": tpl.severity, "params": params})
    return info
