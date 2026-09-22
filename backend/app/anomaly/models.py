"""Anomaly finding representation shared by every rule."""
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from hashlib import sha256
from typing import Any, Dict, List


@dataclass(frozen=True)
class Finding:
    rule_code: str
    subject: str
    severity: str
    summary: str
    transactions: List[Dict[str, Any]]
    amount: Decimal
    occurred_on: date

    @property
    def finding_key(self) -> str:
        return f"{self.rule_code}:{self.subject}"

    @property
    def fingerprint(self) -> str:
        # A reviewer's decision covers the transactions they saw. Hashing the
        # count, total, and transaction identities surfaces a group that
        # gained rows or swapped rows (even at equal value) after review.
        seqs = ",".join(sorted(str(int(t["seq"])) for t in self.transactions))
        raw = f"{len(self.transactions)}:{self.amount}:{seqs}"
        return sha256(raw.encode()).hexdigest()
