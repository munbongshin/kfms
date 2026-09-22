"""Audit rules over corporate-card approvals.

Rules are pure functions over rows already read from v_approval, so they can
be tested with fixture lists instead of a live database.
"""
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Any, Callable, Dict, List, Tuple

from app.anomaly.models import Finding

Row = Dict[str, Any]


def approvals(rows: List[Row]) -> List[Row]:
    """Approvals only. class 'B' rows are cancellations of an earlier approval."""
    return [r for r in rows if (r.get("class") or "").strip() == "A"]


def seq_key(row: Row) -> str:
    """seq arrives as Decimal; normalise so keys stay stable across drivers."""
    return str(int(row["seq"]))


def won(amount: Decimal) -> str:
    return f"{int(amount):,}원"


def to_decimal(value: Any) -> Decimal:
    """Normalise an amount to Decimal.

    Unit-test fixtures pass apprtot as Decimal; DatabaseConnectionPool.execute_query
    (via _json_safe) hands rules a float for the same NUMERIC column on live data.
    Going through str() avoids mixing Decimal and float in arithmetic (which raises
    TypeError) while keeping the value exact. A missing amount becomes Decimal("0")
    rather than raising.
    """
    return Decimal(str(value)) if value is not None else Decimal("0")


@dataclass(frozen=True)
class Rule:
    code: str
    label: str
    severity: str
    detect: Callable[[List[Row], Dict[str, Any]], List[Finding]]
    params: Dict[str, Any] = field(default_factory=dict)
    required_columns: Tuple[str, ...] = ()


def detect_high_amount(rows: List[Row], params: Dict[str, Any]) -> List[Finding]:
    threshold: Decimal = params["threshold"]
    findings = []
    for r in approvals(rows):
        if r["apprtot"] is None or r["apprtot"] < threshold:
            continue
        findings.append(
            Finding(
                rule_code="HIGH_AMOUNT",
                subject=seq_key(r),
                severity="high",
                summary=f"단건 {won(r['apprtot'])}",
                transactions=[r],
                amount=to_decimal(r["apprtot"]),
                occurred_on=date.fromisoformat(r["transdate"]),
            )
        )
    return findings


WEEKDAY_NAMES = ("월", "화", "수", "목", "금", "토", "일")


def detect_off_hours(rows: List[Row], params: Dict[str, Any]) -> List[Finding]:
    night_start: str = params["night_start"]
    night_end: str = params["night_end"]
    findings = []
    for r in approvals(rows):
        if not r.get("transdate") or not r.get("transtime"):
            continue
        occurred = date.fromisoformat(r["transdate"])
        hour = r["transtime"][:2]
        is_weekend = occurred.weekday() >= 5
        is_night = hour >= night_start or hour < night_end
        if not (is_weekend or is_night):
            continue
        label = "주말" if is_weekend else "심야"
        findings.append(
            Finding(
                rule_code="OFF_HOURS",
                subject=seq_key(r),
                severity="medium",
                summary=f"{label} 결제 — {WEEKDAY_NAMES[occurred.weekday()]}요일 {r['transtime'][:5]}",
                transactions=[r],
                amount=to_decimal(r["apprtot"]),
                occurred_on=occurred,
            )
        )
    return findings


def detect_watch_mcc(rows: List[Row], params: Dict[str, Any]) -> List[Finding]:
    watch = set(params["watch_mcc"])
    findings = []
    for r in approvals(rows):
        mcc = r.get("mccname")
        if mcc is None or mcc not in watch:
            continue
        findings.append(
            Finding(
                rule_code="WATCH_MCC",
                subject=seq_key(r),
                severity="high",
                summary=f"주의 업종: {mcc}",
                transactions=[r],
                amount=to_decimal(r["apprtot"]),
                occurred_on=date.fromisoformat(r["transdate"]),
            )
        )
    return findings


def detect_split_payment(rows: List[Row], params: Dict[str, Any]) -> List[Finding]:
    min_count: int = params["min_count"]
    excluded = {b.strip() for b in params["exclude_merchbizno"]}

    groups: Dict[Tuple[str, str, str], List[Row]] = defaultdict(list)
    for r in approvals(rows):
        bizno = (r.get("merchbizno") or "").strip()
        if bizno in excluded:
            continue
        if not r.get("cardno") or not r.get("merchno") or not r.get("transdate"):
            continue
        groups[(r["cardno"], r["merchno"], r["transdate"])].append(r)

    findings = []
    for (cardno, merchno, transdate), members in groups.items():
        if len(members) < min_count:
            continue
        total = sum((to_decimal(m.get("apprtot")) for m in members), Decimal("0"))
        findings.append(
            Finding(
                rule_code="SPLIT_PAYMENT",
                subject=f"{cardno}|{merchno}|{transdate}",
                severity="medium",
                summary=f"동일 가맹점 당일 {len(members)}건 {won(total)}",
                transactions=members,
                amount=total,
                occurred_on=date.fromisoformat(transdate),
            )
        )
    return findings


RULES: List[Rule] = [
    Rule(
        code="HIGH_AMOUNT",
        label="고액 결제",
        severity="high",
        detect=detect_high_amount,
        params={"threshold": Decimal("500000")},
        required_columns=("seq", "class", "apprtot", "transdate"),
    ),
    Rule(
        code="OFF_HOURS",
        label="시간 외 사용",
        severity="medium",
        detect=detect_off_hours,
        params={"night_start": "23", "night_end": "06"},
        required_columns=("seq", "class", "transdate", "transtime"),
    ),
    Rule(
        code="WATCH_MCC",
        label="주의 업종",
        severity="high",
        detect=detect_watch_mcc,
        params={
            "watch_mcc": [
                "상품권 전문판매",
                "볼 링 장",
                "영화관",
                "화   원",
                "기타회원제형태업소4",
                "자사카드발행백화점",
            ]
        },
        required_columns=("seq", "class", "mccname", "transdate"),
    ),
    Rule(
        code="SPLIT_PAYMENT",
        label="분할결제 의심",
        severity="medium",
        detect=detect_split_payment,
        params={"min_count": 2, "exclude_merchbizno": ["1018302925"]},
        required_columns=("seq", "class", "cardno", "merchno", "merchbizno", "transdate", "apprtot"),
    ),
]
