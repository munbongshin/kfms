"""Runs audit rules over a connection's approvals and merges review state."""
from typing import Any, Dict, List, Optional

from app.anomaly.models import Finding
from app.anomaly.rules import RULES
from app.db.repositories.anomaly import AnomalyRepository

SOURCE_VIEW = "v_approval"

SEVERITY_ORDER = {"high": 0, "medium": 1, "low": 2}


def merge_reviews(findings: List[Finding], reviews: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Attach review state; a fingerprint mismatch means the finding changed since review."""
    merged = []
    for f in findings:
        review = reviews.get(f.finding_key)
        merged.append(
            {
                "finding_key": f.finding_key,
                "rule_code": f.rule_code,
                "severity": f.severity,
                "summary": f.summary,
                "amount": float(f.amount),
                "occurred_on": f.occurred_on.isoformat(),
                "transactions": f.transactions,
                "fingerprint": f.fingerprint,
                "review": None
                if review is None
                else {
                    "status": review.status,
                    "note": review.note,
                    "reviewed_at": review.reviewed_at.isoformat(),
                },
                "stale": review is not None and review.fingerprint != f.fingerprint,
            }
        )
    return merged


class AnomalyService:
    def __init__(self, pool, repo: AnomalyRepository):
        self.pool = pool
        self.repo = repo

    async def _load_rows(self, database_id: str) -> List[Dict[str, Any]]:
        return await self.pool.execute_query(database_id, f"SELECT * FROM {SOURCE_VIEW}")

    async def list_findings(
        self,
        database_id: str,
        rule_code: Optional[str] = None,
        status: Optional[str] = None,
    ) -> Dict[str, Any]:
        try:
            rows = await self._load_rows(database_id)
        except Exception as exc:
            return {
                "applicable_rules": [
                    {
                        "rule_code": r.code,
                        "label": r.label,
                        "applicable": False,
                        "caveat": f"{SOURCE_VIEW} 조회 실패: {exc}",
                    }
                    for r in RULES
                ],
                "findings": [],
            }

        available = set(rows[0].keys()) if rows else set()

        applicable_rules: List[Dict[str, Any]] = []
        findings: List[Finding] = []

        for rule in RULES:
            if rule_code and rule.code != rule_code:
                continue

            missing = [c for c in rule.required_columns if c not in available]
            if rows and missing:
                applicable_rules.append(
                    {
                        "rule_code": rule.code,
                        "label": rule.label,
                        "applicable": False,
                        "caveat": f"컬럼 없음: {', '.join(missing)}",
                    }
                )
                continue

            try:
                detected = rule.detect(rows, rule.params)
            except Exception as exc:
                # Rules are independent; one failure must not blank the screen.
                applicable_rules.append(
                    {
                        "rule_code": rule.code,
                        "label": rule.label,
                        "applicable": False,
                        "caveat": f"규칙 실행 오류: {exc}",
                    }
                )
                continue

            entry: Dict[str, Any] = {"rule_code": rule.code, "label": rule.label, "applicable": True}
            if rule.code == "WATCH_MCC":
                unclassified = sum(
                    1 for r in rows if (r.get("class") or "").strip() == "A" and r.get("mccname") is None
                )
                if unclassified:
                    entry["caveat"] = f"업종 미분류 {unclassified}건은 판정에서 제외됨"
            applicable_rules.append(entry)
            findings.extend(detected)

        reviews = await self.repo.get_reviews(database_id, [f.finding_key for f in findings])
        merged = merge_reviews(findings, reviews)

        if status == "unreviewed":
            merged = [m for m in merged if m["review"] is None or m["stale"]]
        elif status in ("confirmed", "dismissed"):
            merged = [m for m in merged if m["review"] and m["review"]["status"] == status]

        merged.sort(key=lambda m: (SEVERITY_ORDER.get(m["severity"], 9), m["occurred_on"]))
        return {"applicable_rules": applicable_rules, "findings": merged}
