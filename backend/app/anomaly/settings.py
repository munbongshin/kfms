"""Editable anomaly thresholds.

The rules' logic stays in code; only these numbers, switches and lists can be
changed from the screen. Everything is validated before it is stored — an empty
list, a zero amount, or every check switched off would quietly turn a rule into
one that finds nothing.

Every rule can be switched off (`enabled`) and given another severity; beyond
that each rule exposes the values that shape what it finds.
"""
from dataclasses import replace
from datetime import date
from decimal import Decimal
from typing import Any, Dict, List, Tuple

MAX_AMOUNT = 10 ** 12
MAX_LIST = 200
MAX_HOLIDAYS = 400
MAX_CATEGORIES = 100
MAX_WINDOW_MINUTES = 24 * 60

SEVERITIES = (("high", "높음"), ("medium", "보통"), ("low", "낮음"))

_COMMON = {
    "enabled": ("bool", "사용", "끄면 이 규칙으로는 점검하지 않습니다"),
    "severity": ("severity", "심각도", "결과 목록의 정렬과 표시에 쓰입니다"),
}

# template -> parameter -> (kind, label, hint)
EDITABLE: Dict[str, Dict[str, Tuple[str, str, str]]] = {
    "HIGH_AMOUNT": {
        **_COMMON,
        "threshold": ("number", "기준 금액(원)", "한 건이 이 금액 이상이면 고액 결제"),
        "category_thresholds": (
            "amountmap", "업종별 기준 금액",
            "이 업종은 위 기준 대신 여기 금액을 씁니다 (업종명은 결과의 업종 표기와 같게)",
        ),
    },
    "OFF_HOURS": {
        **_COMMON,
        "check_weekend": ("bool", "주말 점검", "토·일요일 결제를 시간 외로 봅니다"),
        "check_holiday": ("bool", "공휴일 점검", "아래 공휴일 목록의 날짜 결제를 시간 외로 봅니다"),
        "holidays": ("dates", "공휴일 목록", "날짜를 한 줄에 하나씩 (예: 2026-05-05)"),
        "check_night": ("bool", "심야 점검", "심야 시간대 결제를 시간 외로 봅니다"),
        "night_start": ("hour", "심야 시작(시)", "이 시각부터 심야 (0~23)"),
        "night_end": ("hour", "심야 종료(시)", "이 시각 전까지 심야 (0~23)"),
    },
    "WATCH_MCC": {
        **_COMMON,
        "watch_mcc": ("list", "주의 업종", "업종명을 한 줄에 하나씩"),
    },
    "SPLIT_PAYMENT": {
        **_COMMON,
        "min_count": ("count", "최소 건수", "같은 카드·가맹점·날짜에 이 건수 이상이면 분할결제 의심"),
        "min_total": ("amount0", "합계 금액 기준(원)", "묶인 결제의 합계가 이 금액 이상일 때만 (0이면 금액은 보지 않음)"),
        "window_minutes": ("minutes", "묶는 시간(분)", "앞 결제와 이 시간 안에 이어진 결제만 한 묶음 (0이면 하루 전체)"),
        "exclude_merchbizno": ("list", "제외 사업자번호", "분할결제로 보지 않을 가맹점 사업자번호"),
    },
}

# What the screen draws for each kind of parameter.
_CONTROL = {
    "number": "number", "count": "number", "hour": "number", "amount0": "number", "minutes": "number",
    "bool": "switch", "severity": "choice", "amountmap": "map", "list": "list", "dates": "list",
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


def _clean_dates(value: Any) -> List[str]:
    days = _clean_list(value)
    if len(days) > MAX_HOLIDAYS:
        raise ValueError
    for day in days:
        if len(day) != 10:
            raise ValueError
        date.fromisoformat(day)  # rejects 2023-02-30 and anything not ISO
    return sorted(days)


def _clean_amount_map(value: Any) -> Dict[str, int]:
    if not isinstance(value, dict) or len(value) > MAX_CATEGORIES:
        raise ValueError
    out: Dict[str, int] = {}
    for key, amount in value.items():
        name = str(key).strip()
        if not name or len(name) > 100:
            raise ValueError
        n = _int(amount)
        if not 1 <= n <= MAX_AMOUNT:
            raise ValueError
        out[name] = n
    return out


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
                elif kind == "amount0":
                    n = _int(value)
                    if not 0 <= n <= MAX_AMOUNT:
                        raise ValueError
                    parsed = n
                elif kind == "minutes":
                    n = _int(value)
                    if not 0 <= n <= MAX_WINDOW_MINUTES:
                        raise ValueError
                    parsed = n
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
                elif kind == "bool":
                    if not isinstance(value, bool):
                        raise ValueError
                    parsed = value
                elif kind == "severity":
                    if value not in {v for v, _ in SEVERITIES}:
                        raise ValueError
                    parsed = value
                elif kind == "amountmap":
                    parsed = _clean_amount_map(value)
                elif kind == "dates":
                    parsed = _clean_dates(value)
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

    # With every check off, an enabled rule would look active and find nothing.
    off = clean.get("OFF_HOURS", {})
    checks = ("check_weekend", "check_holiday", "check_night")
    if all(k in off for k in checks) and not any(off[k] for k in checks) and off.get("enabled", True):
        errors.append("시간 외 사용: 주말·공휴일·심야 중 하나는 켜 두세요 (규칙을 쉬려면 '사용'을 끄세요)")

    return clean, errors


def without_defaults(templates, clean: Dict[str, Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """Only the values that differ from the built-in defaults, so that setting a
    field back to its default really resets it (and follows a future default)."""
    kept: Dict[str, Dict[str, Any]] = {}
    for rule in describe(templates, {}):
        for param in rule["params"]:
            value = (clean.get(rule["template"]) or {}).get(param["key"])
            if value is None:
                continue
            comparable = int(value) if param["unit"] == "hour" else value
            if comparable != param["default"]:
                kept.setdefault(rule["template"], {})[param["key"]] = value
    return kept


def apply_overrides(templates, overrides: Dict[str, Dict[str, Any]]):
    """New templates with the overrides merged in; the originals are untouched."""
    out = []
    for tpl in templates:
        changes = overrides.get(tpl.template)
        if not changes:
            out.append(tpl)
            continue
        params = dict(tpl.params)
        severity = tpl.severity
        for key, value in changes.items():
            if key == "severity":
                severity = value
            elif key == "threshold":
                params[key] = Decimal(str(value))
            elif key == "category_thresholds":
                params[key] = {name: Decimal(str(v)) for name, v in value.items()}
            else:
                params[key] = value
        out.append(replace(tpl, params=params, severity=severity))
    return out


def _default_of(tpl, key: str, kind: str) -> Any:
    if key == "severity":
        return tpl.severity
    default = tpl.params.get(key)
    if kind == "amountmap":
        return {name: int(v) for name, v in (default or {}).items()}
    if isinstance(default, Decimal):
        return int(default)
    if kind == "hour":
        return int(default)
    return default


def describe(templates, overrides: Dict[str, Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Every editable parameter with its current value and its default."""
    info = []
    for tpl in templates:
        spec = EDITABLE.get(tpl.template)
        if not spec:
            continue
        params = []
        for key, (kind, label, hint) in spec.items():
            default = _default_of(tpl, key, kind)
            value = (overrides.get(tpl.template) or {}).get(key, default)
            if kind == "hour":
                value = int(value)
            entry = {
                "key": key,
                "label": label,
                "hint": hint,
                "kind": _CONTROL[kind],
                "unit": kind,
                "value": value,
                "default": default,
            }
            if kind == "severity":
                entry["options"] = [{"value": v, "label": name} for v, name in SEVERITIES]
            params.append(entry)
        info.append({
            "template": tpl.template,
            "label": tpl.label,
            "severity": (overrides.get(tpl.template) or {}).get("severity", tpl.severity),
            "params": params,
        })
    return info
