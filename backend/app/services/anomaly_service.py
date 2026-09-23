"""Runs audit rules over a connection's approvals and merges review state."""
import logging
import re
from typing import Any, Dict, List, Optional

from app.anomaly.models import Finding
from app.anomaly.rules import (
    AMOUNT,
    CARD,
    CATEGORY,
    CLASS,
    DATE,
    KEY,
    MERCHANT,
    MERCHANT_BIZNO,
    TIME,
    RULES,
    SOURCES,
    Source,
    detect_watch_mcc,
    rules_by_source,
)
from app.db.repositories.anomaly import AnomalyRepository

logger = logging.getLogger(__name__)

SEVERITY_ORDER = {"high": 0, "medium": 1, "low": 2}

# I2: only these transaction fields reach the browser. The rules keep the full
# rows (Finding.fingerprint hashes the member seq values and the summaries are
# built from row fields), but shipping SELECT * would leak card numbers,
# merchant business numbers and everything else the view happens to carry.
TRANSACTION_FIELDS = ("seq", "merchname", "apprtot")

# I4: caveats are rendered in the UI, so they never carry exception text —
# SQLAlchemy messages embed SQL and connection details. The detail is logged.
SOURCE_ERROR_CAVEAT = "점검 대상 조회 실패 — 서버 로그를 확인하세요"
RULE_ERROR_CAVEAT = "규칙 실행 오류 — 서버 로그를 확인하세요"
REVIEW_ERROR_CAVEAT = "검토 이력을 불러오지 못해 모든 건이 미검토로 표시됩니다"


# Shown by default when a reviewer expands a finding. The card number is
# deliberately unmasked: the reviewer opened this row to judge it, and the
# list endpoint still never carries it.
#
# The first group is addressed through the source's logical mapping, so the
# same labels work whether the column is called transdate or apprdate. The
# second is physical and simply skipped where a source lacks it.
LOGICAL_DETAIL = (
    (CARD, "카드번호"),
    (CLASS, "구분"),
    (DATE, "사용일자"),
    (TIME, "사용시각"),
    (AMOUNT, "금액"),
    (CATEGORY, "업종"),
    (MERCHANT, "가맹점번호"),
    (MERCHANT_BIZNO, "가맹점 사업자번호"),
)

EXTRA_DETAIL = (
    ("merchname", "가맹점명"),
    ("apprno", "승인번호"),
    ("appramt", "공급가액"),
    ("vat", "부가세"),
    ("insttype", "할부구분"),
    ("instmonth", "할부개월"),
    ("merchtel", "가맹점 전화"),
    ("merchaddr1", "가맹점 주소"),
)


ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def build_source_query(source: Source, date_from: Optional[str], date_to: Optional[str]):
    """SELECT for one source, bounded by an optional period.

    The date columns are CHAR(10) 'YYYY-MM-DD', so lexicographic comparison is
    date comparison and no cast is needed. The bounds are bind parameters; the
    column name comes from the Source catalogue, never from a request.
    """
    for label, value in (("date_from", date_from), ("date_to", date_to)):
        if value is not None and not ISO_DATE.match(value):
            raise ValueError(f"{label} must be YYYY-MM-DD, got {value!r}")

    if date_from and date_to and date_from > date_to:
        raise ValueError(f"date_from {date_from} is after date_to {date_to}")

    conditions = []
    params: Dict[str, Any] = {}
    if date_from:
        conditions.append(f"{source.columns[DATE]} >= :date_from")
        params["date_from"] = date_from
    if date_to:
        conditions.append(f"{source.columns[DATE]} <= :date_to")
        params["date_to"] = date_to

    sql = f"SELECT * FROM {source.view}"
    if conditions:
        sql += " WHERE " + " AND ".join(conditions)
    return sql, params


def _public_transaction(row: Dict[str, Any]) -> Dict[str, Any]:
    """The spec's response example: seq, merchname, apprtot — nothing else."""
    return {field: row.get(field) for field in TRANSACTION_FIELDS}


def split_detail(row: Dict[str, Any], source: Source) -> tuple:
    """Split one row into the audit fields and everything else worth showing.

    Core fields keep their order and survive a null value — a missing 업종 is
    itself evidence. The rest drops empties so the "show all" toggle is not
    mostly blank.
    """
    core = []
    seen = set()

    for logical, label in LOGICAL_DETAIL:
        physical = source.columns.get(logical)
        if physical is None:
            continue
        core.append({"field": physical, "label": label, "value": row.get(physical)})
        seen.add(physical)

    for physical, label in EXTRA_DETAIL:
        if physical in row and physical not in seen:
            core.append({"field": physical, "label": label, "value": row.get(physical)})
            seen.add(physical)

    rest = [
        {"field": field, "label": field, "value": value}
        for field, value in row.items()
        if field not in seen and value is not None and value != ""
    ]
    return core, rest


def merge_reviews(
    findings: List[Finding], reviews: Dict[str, Any], source_of: Optional[Dict[str, str]] = None
) -> List[Dict[str, Any]]:
    """Attach review state; a fingerprint mismatch means the finding changed since review."""
    merged = []
    for f in findings:
        review = reviews.get(f.finding_key)
        merged.append(
            {
                "finding_key": f.finding_key,
                "rule_code": f.rule_code,
                "source": (source_of or {}).get(f.rule_code, ""),
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

    async def _load_rows(
        self,
        database_id: str,
        source: Source,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        sql, params = build_source_query(source, date_from, date_to)
        return await self.pool.execute_query(database_id, sql, params)

    async def list_sources(self, database_id: str) -> List[Dict[str, Any]]:
        """Checkable sources for this connection, each with the period it covers.

        A source is checkable only if its view is actually queryable here — the
        rules are written against specific columns, so "every table" was never
        the answer. The screen seeds its date picker from the range.
        """
        out = []
        for source in SOURCES.values():
            try:
                rows = await self.pool.execute_query(
                    database_id,
                    f"SELECT MIN({source.columns[DATE]}) AS min_date,"
                    f" MAX({source.columns[DATE]}) AS max_date,"
                    f" COUNT(*) AS row_count FROM {source.view}",
                )
            except Exception:
                logger.exception(
                    "Anomaly source %s unavailable for database_id=%s", source.key, database_id
                )
                continue

            row = rows[0] if rows else {}
            out.append(
                {
                    "key": source.key,
                    "label": source.label,
                    "min_date": row.get("min_date"),
                    "max_date": row.get("max_date"),
                    "row_count": int(row.get("row_count") or 0),
                }
            )
        return out

    async def get_transactions(
        self, database_id: str, source_key: str, keys: List[int]
    ) -> List[Dict[str, Any]]:
        """Full rows behind one finding, split into audit fields and the rest.

        Only reached when a reviewer expands a row, which is why this — unlike
        the list endpoint — may carry the card number.
        """
        if not keys:
            return []

        source = SOURCES[source_key]
        key_column = source.columns[KEY]
        placeholders = ", ".join(f":key{i}" for i in range(len(keys)))
        params = {f"key{i}": key for i, key in enumerate(keys)}
        rows = await self.pool.execute_query(
            database_id,
            f"SELECT * FROM {source.view} WHERE {key_column} IN ({placeholders})",
            params,
        )

        by_key = {int(row[key_column]): row for row in rows}
        detail = []
        for key in keys:
            row = by_key.get(key)
            if row is None:
                continue
            core, rest = split_detail(row, source)
            detail.append({"seq": key, "core": core, "rest": rest})
        return detail

    def _run_source_rules(
        self,
        database_id: str,
        source_rules,
        rows: List[Dict[str, Any]],
        template: Optional[str],
        applicable_rules: List[Dict[str, Any]],
        findings: List[Finding],
    ) -> None:
        """Run one source's rules over its rows, recording applicability as it goes."""
        available = set(rows[0].keys()) if rows else set()

        for rule in source_rules:
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
                        "template": rule.template,
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
                        "template": rule.template,
                        "label": rule.label,
                        "applicable": False,
                        "caveat": RULE_ERROR_CAVEAT,
                    }
                )
                continue

            entry: Dict[str, Any] = {
                "rule_code": rule.code,
                "template": rule.template,
                "label": rule.label,
                "applicable": True,
            }
            if rule.detect is detect_watch_mcc:
                category = rule.params["columns"][CATEGORY]
                klass = rule.params["columns"][CLASS]
                unclassified = sum(
                    1 for r in rows if (r.get(klass) or "").strip() == "A" and r.get(category) is None
                )
                if unclassified:
                    entry["caveat"] = f"업종 미분류 {unclassified}건은 판정에서 제외됨"
            applicable_rules.append(entry)

            if template and rule.template != template:
                continue
            findings.extend(detected)

    async def list_findings(
        self,
        database_id: str,
        template: Optional[str] = None,
        status: Optional[str] = None,
        source: Optional[str] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
    ) -> Dict[str, Any]:
        grouped = rules_by_source(RULES)
        if source:
            grouped = {k: v for k, v in grouped.items() if k == source}

        applicable_rules: List[Dict[str, Any]] = []
        findings: List[Finding] = []

        # Each source is read once and handed to every rule that declares it, so
        # adding a rule on a new source costs one SOURCES entry, not a rewrite.
        for source_key, source_rules in grouped.items():
            definition = SOURCES[source_key]
            try:
                rows = await self._load_rows(database_id, definition, date_from, date_to)
            except ValueError as exc:
                raise exc
            except Exception:
                logger.exception(
                    "Anomaly source query failed for database_id=%s (%s)",
                    database_id,
                    definition.view,
                )
                applicable_rules.extend(
                    {
                        "rule_code": r.code,
                        "template": r.template,
                        "label": r.label,
                        "applicable": False,
                        "caveat": SOURCE_ERROR_CAVEAT,
                    }
                    for r in source_rules
                )
                continue

            self._run_source_rules(
                database_id, source_rules, rows, template, applicable_rules, findings
            )

        # C2: the metadata DB is a second failure domain. A missing anomaly_review
        # table or a kfms outage must degrade to "nothing reviewed yet", not a 500
        # that blanks the screen — the same contract _load_rows already honours for
        # the retail side. The degradation is surfaced, not swallowed.
        source_of = {r.code: r.source for r in RULES}

        caveat: Optional[str] = None
        try:
            reviews = await self.repo.get_reviews(
                database_id, [f.finding_key for f in findings]
            )
        except Exception:
            logger.exception(
                "Anomaly review lookup failed for database_id=%s; rendering findings "
                "without review state",
                database_id,
            )
            reviews = {}
            caveat = REVIEW_ERROR_CAVEAT

        merged = merge_reviews(findings, reviews, source_of)

        if status == "unreviewed":
            merged = [m for m in merged if m["review"] is None or m["stale"]]
        elif status in ("confirmed", "dismissed"):
            merged = [m for m in merged if m["review"] and m["review"]["status"] == status]

        merged.sort(key=lambda m: (SEVERITY_ORDER.get(m["severity"], 9), m["occurred_on"]))
        return {"applicable_rules": applicable_rules, "findings": merged, "caveat": caveat}
