"""Runs audit rules over a connection's approvals and merges review state."""
import logging
from typing import Any, Dict, List, Optional

from app.anomaly.models import Finding
from app.anomaly.rules import RULES
from app.db.repositories.anomaly import AnomalyRepository

logger = logging.getLogger(__name__)

SOURCE_VIEW = "v_approval"

SEVERITY_ORDER = {"high": 0, "medium": 1, "low": 2}

# I2: only these transaction fields reach the browser. The rules keep the full
# rows (Finding.fingerprint hashes the member seq values and the summaries are
# built from row fields), but shipping SELECT * would leak card numbers,
# merchant business numbers and everything else the view happens to carry.
TRANSACTION_FIELDS = ("seq", "merchname", "apprtot")

# I4: caveats are rendered in the UI, so they never carry exception text —
# SQLAlchemy messages embed SQL and connection details. The detail is logged.
SOURCE_ERROR_CAVEAT = f"{SOURCE_VIEW} 조회 실패 — 서버 로그를 확인하세요"
RULE_ERROR_CAVEAT = "규칙 실행 오류 — 서버 로그를 확인하세요"
REVIEW_ERROR_CAVEAT = "검토 이력을 불러오지 못해 모든 건이 미검토로 표시됩니다"


# Shown by default when a reviewer expands a finding. The card number is
# deliberately unmasked: the reviewer opened this row to judge it, and the
# list endpoint still never carries it.
DETAIL_LABELS = {
    "cardno": "카드번호",
    "class": "구분",
    "transdate": "사용일자",
    "transtime": "사용시각",
    "merchname": "가맹점명",
    "mccname": "업종",
    "apprtot": "승인금액",
    "appramt": "공급가액",
    "vat": "부가세",
    "apprno": "승인번호",
    "insttype": "할부구분",
    "instmonth": "할부개월",
    "merchbizno": "가맹점 사업자번호",
    "merchtel": "가맹점 전화",
    "merchaddr1": "가맹점 주소",
}
DETAIL_FIELDS = tuple(DETAIL_LABELS)


def _public_transaction(row: Dict[str, Any]) -> Dict[str, Any]:
    """The spec's response example: seq, merchname, apprtot — nothing else."""
    return {field: row.get(field) for field in TRANSACTION_FIELDS}


def split_detail(row: Dict[str, Any]) -> tuple:
    """Split one approval into the audit fields and everything else worth showing.

    Core fields keep their order and survive a null value — a missing 업종 is
    itself evidence. The rest drops empties so the "show all" toggle is not
    mostly blank.
    """
    core = [
        {"field": field, "label": DETAIL_LABELS[field], "value": row.get(field)}
        for field in DETAIL_FIELDS
    ]
    rest = [
        {"field": field, "label": field, "value": value}
        for field, value in row.items()
        if field not in DETAIL_LABELS and value is not None and value != ""
    ]
    return core, rest


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
                "transactions": [_public_transaction(t) for t in f.transactions],
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

    async def get_transactions(self, database_id: str, seqs: List[int]) -> List[Dict[str, Any]]:
        """Full approvals behind one finding, split into audit fields and the rest.

        Only reached when a reviewer expands a row, which is why this — unlike
        the list endpoint — may carry the card number.
        """
        if not seqs:
            return []

        placeholders = ", ".join(f":seq{i}" for i in range(len(seqs)))
        params = {f"seq{i}": seq for i, seq in enumerate(seqs)}
        rows = await self.pool.execute_query(
            database_id,
            f"SELECT * FROM {SOURCE_VIEW} WHERE seq IN ({placeholders})",
            params,
        )

        by_seq = {int(row["seq"]): row for row in rows}
        detail = []
        for seq in seqs:
            row = by_seq.get(seq)
            if row is None:
                continue
            core, rest = split_detail(row)
            detail.append({"seq": seq, "core": core, "rest": rest})
        return detail

    async def list_findings(
        self,
        database_id: str,
        rule_code: Optional[str] = None,
        status: Optional[str] = None,
    ) -> Dict[str, Any]:
        try:
            rows = await self._load_rows(database_id)
        except Exception:
            logger.exception(
                "Anomaly source query failed for database_id=%s (%s)", database_id, SOURCE_VIEW
            )
            return {
                "applicable_rules": [
                    {
                        "rule_code": r.code,
                        "label": r.label,
                        "applicable": False,
                        "caveat": SOURCE_ERROR_CAVEAT,
                    }
                    for r in RULES
                ],
                "findings": [],
                "caveat": None,
            }

        available = set(rows[0].keys()) if rows else set()

        applicable_rules: List[Dict[str, Any]] = []
        findings: List[Finding] = []

        for rule in RULES:
            # I5: every rule always produces an applicable_rules entry — the screen
            # builds its filter dropdown from this array, so skipping non-matching
            # rules here collapsed the dropdown to the one rule already selected and
            # made the WATCH_MCC 미분류 caveat vanish. rule_code only decides which
            # findings are kept, below.
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
            except Exception:
                # Rules are independent; one failure must not blank the screen.
                logger.exception(
                    "Anomaly rule %s failed for database_id=%s", rule.code, database_id
                )
                applicable_rules.append(
                    {
                        "rule_code": rule.code,
                        "label": rule.label,
                        "applicable": False,
                        "caveat": RULE_ERROR_CAVEAT,
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

            if rule_code and rule.code != rule_code:
                continue
            findings.extend(detected)

        # C2: the metadata DB is a second failure domain. A missing anomaly_review
        # table or a kfms outage must degrade to "nothing reviewed yet", not a 500
        # that blanks the screen — the same contract _load_rows already honours for
        # the retail side. The degradation is surfaced, not swallowed.
        caveat: Optional[str] = None
        try:
            reviews = await self.repo.get_reviews(database_id, [f.finding_key for f in findings])
        except Exception:
            logger.exception(
                "Anomaly review lookup failed for database_id=%s; rendering findings "
                "without review state",
                database_id,
            )
            reviews = {}
            caveat = REVIEW_ERROR_CAVEAT

        merged = merge_reviews(findings, reviews)

        if status == "unreviewed":
            merged = [m for m in merged if m["review"] is None or m["stale"]]
        elif status in ("confirmed", "dismissed"):
            merged = [m for m in merged if m["review"] and m["review"]["status"] == status]

        merged.sort(key=lambda m: (SEVERITY_ORDER.get(m["severity"], 9), m["occurred_on"]))
        return {"applicable_rules": applicable_rules, "findings": merged, "caveat": caveat}
