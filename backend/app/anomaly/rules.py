"""Audit rules over corporate-card approvals.

Rules are pure functions over rows already read from v_approval, so they can
be tested with fixture lists instead of a live database.
"""
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
                amount=r["apprtot"],
                occurred_on=date.fromisoformat(r["transdate"]),
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
]
