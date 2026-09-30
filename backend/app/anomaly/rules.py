"""Audit rules over corporate-card data.

Rules are pure functions over rows already read from a source view, so they can
be tested with fixture lists instead of a live database.

A rule never names a physical column. It asks its Source for a logical one —
"date", "amount", "merchant" — so the same rule runs against 승인내역, 매입내역
and 청구내역, which carry the same facts under different column names. Adding a
source is a SOURCES entry; the rules do not change.
"""
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Any, Callable, Dict, List, Tuple

from app.anomaly.holidays_kr import holiday_of
from app.anomaly.models import Finding

Row = Dict[str, Any]

# Logical column names a rule may ask for. A source that cannot supply one
# simply does not offer the rules that need it.
KEY = "key"
CLASS = "class"
DATE = "date"
TIME = "time"
AMOUNT = "amount"
CARD = "card"
MERCHANT = "merchant"
MERCHANT_BIZNO = "merchant_bizno"
CATEGORY = "category"


@dataclass(frozen=True)
class Source:
    """A view that can be checked, and the physical names behind the logical ones.

    `code_prefix` keeps rule codes distinct across sources. finding_key carries
    no source, so two sources sharing a rule code would collide in one key and
    a reviewer's decision would cross over between tables.
    """

    key: str
    label: str
    view: str
    columns: Dict[str, str]
    code_prefix: str = ""
    caveat: str = ""

    def has(self, *logical: str) -> bool:
        return all(name in self.columns for name in logical)


SOURCES: Dict[str, Source] = {
    "approval": Source(
        key="approval",
        label="승인내역",
        view="v_approval",
        columns={
            KEY: "seq",
            CLASS: "class",
            DATE: "transdate",
            TIME: "transtime",
            AMOUNT: "apprtot",
            CARD: "cardno",
            MERCHANT: "merchno",
            MERCHANT_BIZNO: "merchbizno",
            CATEGORY: "mccname",
        },
    ),
    "acquire": Source(
        key="acquire",
        label="매입내역",
        view="v_acquire",
        code_prefix="ACQUIRE_",
        columns={
            KEY: "seq",
            CLASS: "class",
            DATE: "apprdate",
            TIME: "purchtime",
            AMOUNT: "apprtot",
            CARD: "cardno",
            MERCHANT: "merchno",
            MERCHANT_BIZNO: "merchbizno",
            CATEGORY: "mccname",
        },
        caveat="매입내역은 거래시각이 일부 건에만 있어 시간 외 사용 판정이 제한적입니다",
    ),
    # No TIME: origintranstime is empty on every row, so offering 시간 외 사용
    # here would look applicable while never finding anything. No MERCHANT or
    # CATEGORY either — v_bill carries neither merchno nor mccname.
    "bill": Source(
        key="bill",
        label="청구내역",
        view="v_bill",
        code_prefix="BILL_",
        columns={
            KEY: "seq",
            CLASS: "class",
            DATE: "orgnapprdate",
            AMOUNT: "biltot",
            CARD: "cardno",
            MERCHANT_BIZNO: "merchbizno",
        },
    ),
}


def col(params: Dict[str, Any], logical: str) -> str:
    return params["columns"][logical]


def val(row: Row, params: Dict[str, Any], logical: str, default: Any = None) -> Any:
    return row.get(col(params, logical), default)


def approvals(rows: List[Row], params: Dict[str, Any]) -> List[Row]:
    """Class 'A' only. 'B' rows are cancellations referencing an earlier record."""
    return [r for r in rows if (val(r, params, CLASS) or "").strip() == "A"]


def row_key(row: Row, params: Dict[str, Any]) -> str:
    """The identifying number arrives as Decimal or float; normalise it."""
    return str(int(val(row, params, KEY)))


def won(amount: Decimal) -> str:
    return f"{int(amount):,}원"


def to_decimal(value: Any) -> Decimal:
    """Normalise an amount to Decimal.

    Unit-test fixtures pass amounts as Decimal; DatabaseConnectionPool.execute_query
    (via _json_safe) hands rules a float for the same NUMERIC column on live data.
    Going through str() avoids mixing Decimal and float in arithmetic (which raises
    TypeError) while keeping the value exact. A missing amount becomes Decimal("0").
    """
    return Decimal(str(value)) if value is not None else Decimal("0")


def detect_high_amount(rows: List[Row], params: Dict[str, Any]) -> List[Finding]:
    threshold: Decimal = params["threshold"]
    # A category may have its own line (식비 30만원, 항공사 200만원). A source
    # with no category column simply has none, and uses the default for all.
    by_category: Dict[str, Any] = params.get("category_thresholds") or {}
    category_column = params["columns"].get(CATEGORY)
    findings = []
    for r in approvals(rows, params):
        occurred = val(r, params, DATE)
        amount = val(r, params, AMOUNT)
        if not occurred or amount is None:
            continue
        limit, note = threshold, ""
        category = r.get(category_column) if category_column else None
        if category is not None and category in by_category:
            limit = to_decimal(by_category[category])
            note = f" ({category} 기준 {won(limit)} 이상)"
        if to_decimal(amount) < limit:
            continue
        findings.append(
            Finding(
                rule_code=params["code"],
                subject=row_key(r, params),
                severity=params["severity"],
                summary=f"단건 {won(to_decimal(amount))}{note}",
                transactions=[r],
                amount=to_decimal(amount),
                occurred_on=date.fromisoformat(occurred),
            )
        )
    return findings


WEEKDAY_NAMES = ("월", "화", "수", "목", "금", "토", "일")


def detect_off_hours(rows: List[Row], params: Dict[str, Any]) -> List[Finding]:
    night_start: str = params["night_start"]
    night_end: str = params["night_end"]
    # Each kind can be switched off on its own; all default to on.
    check_weekend = params.get("check_weekend", True)
    check_night = params.get("check_night", True)
    check_holiday = params.get("check_holiday", True)
    # Official holidays apply by themselves; the lists add days and remove days.
    auto_holidays = params.get("auto_holidays", True)
    extra_holidays = params.get("holidays") or []
    removed_holidays = params.get("holiday_exceptions") or []
    # Days received by the sync (announced temporary holidays); not edited on screen.
    synced_holidays = params.get("synced_holidays") or {}
    findings = []
    for r in approvals(rows, params):
        day = val(r, params, DATE)
        clock = val(r, params, TIME)
        if not day or not clock:
            continue
        occurred = date.fromisoformat(day)
        hour = clock[:2]
        holiday_name = holiday_of(day, auto_holidays, extra_holidays, removed_holidays, synced_holidays) if check_holiday else None
        is_holiday = holiday_name is not None
        is_weekend = check_weekend and occurred.weekday() >= 5
        is_night = check_night and (hour >= night_start or hour < night_end)
        if not (is_holiday or is_weekend or is_night):
            continue
        label = "공휴일" if is_holiday else "주말" if is_weekend else "심야"
        if is_holiday and holiday_name:
            label = f"공휴일({holiday_name})"
        findings.append(
            Finding(
                rule_code=params["code"],
                subject=row_key(r, params),
                severity=params["severity"],
                summary=f"{label} 결제 — {WEEKDAY_NAMES[occurred.weekday()]}요일 {clock[:5]}",
                transactions=[r],
                amount=to_decimal(val(r, params, AMOUNT)),
                occurred_on=occurred,
            )
        )
    return findings


def detect_watch_mcc(rows: List[Row], params: Dict[str, Any]) -> List[Finding]:
    watch = set(params["watch_mcc"])
    findings = []
    for r in approvals(rows, params):
        day = val(r, params, DATE)
        category = val(r, params, CATEGORY)
        if not day or category is None or category not in watch:
            continue
        findings.append(
            Finding(
                rule_code=params["code"],
                subject=row_key(r, params),
                severity=params["severity"],
                summary=f"주의 업종: {category}",
                transactions=[r],
                amount=to_decimal(val(r, params, AMOUNT)),
                occurred_on=date.fromisoformat(day),
            )
        )
    return findings


def minutes_of(clock: Any) -> Any:
    """Minutes since midnight from 'HH:MM[:SS]', or None when it cannot be read."""
    try:
        return int(str(clock)[0:2]) * 60 + int(str(clock)[3:5])
    except (ValueError, TypeError):
        return None


def bursts(members: List[Row], params: Dict[str, Any], window: int) -> List[List[Row]]:
    """Split one day's payments into runs where each is within `window` minutes
    of the one before. Payments with no readable time cannot be placed and are left out."""
    timed = []
    for m in members:
        minute = minutes_of(val(m, params, TIME))
        if minute is not None:
            timed.append((minute, m))
    timed.sort(key=lambda pair: pair[0])

    runs: List[List[Row]] = []
    last = None
    for minute, m in timed:
        if last is None or minute - last > window:
            runs.append([])
        runs[-1].append(m)
        last = minute
    return runs


def detect_split_payment(rows: List[Row], params: Dict[str, Any]) -> List[Finding]:
    min_count: int = params["min_count"]
    excluded = {b.strip() for b in params["exclude_merchbizno"]}
    min_total = to_decimal(params.get("min_total") or 0)
    # 0 means the whole day is one group, as before. A source without a time of
    # day cannot be windowed either.
    window = int(params.get("window_minutes") or 0) if TIME in params["columns"] else 0

    groups: Dict[Tuple[str, str, str], List[Row]] = defaultdict(list)
    for r in approvals(rows, params):
        bizno = (val(r, params, MERCHANT_BIZNO) or "").strip()
        if bizno in excluded:
            continue
        card = val(r, params, CARD)
        merchant = val(r, params, MERCHANT)
        day = val(r, params, DATE)
        if not card or not merchant or not day:
            continue
        groups[(card, merchant, day)].append(r)

    findings = []
    for (card, merchant, day), members in groups.items():
        for run in (bursts(members, params, window) if window else [members]):
            if len(run) < min_count:
                continue
            total = sum((to_decimal(val(m, params, AMOUNT)) for m in run), Decimal("0"))
            if total < min_total:
                continue
            # A windowed group is named by its first payment, so two bursts on
            # one day are two findings a reviewer can judge separately.
            subject = f"{card}|{merchant}|{day}"
            span = f"당일 {len(run)}건"
            if window:
                subject += f"|{str(val(run[0], params, TIME))[:5]}"
                span = f"{window}분 이내 {len(run)}건"
            findings.append(
                Finding(
                    rule_code=params["code"],
                    subject=subject,
                    severity=params["severity"],
                    summary=f"동일 가맹점 {span} {int(total):,}원",
                    transactions=run,
                    amount=total,
                    occurred_on=date.fromisoformat(day),
                )
            )
    return findings


@dataclass(frozen=True)
class RuleTemplate:
    """A rule before it is bound to a source."""

    template: str
    label: str
    severity: str
    detect: Callable[[List[Row], Dict[str, Any]], List[Finding]]
    requires: Tuple[str, ...]
    params: Dict[str, Any] = field(default_factory=dict)


TEMPLATES: List[RuleTemplate] = [
    RuleTemplate(
        template="HIGH_AMOUNT",
        label="고액 결제",
        severity="high",
        detect=detect_high_amount,
        requires=(KEY, CLASS, DATE, AMOUNT),
        params={"threshold": Decimal("500000"), "category_thresholds": {}, "enabled": True},
    ),
    RuleTemplate(
        template="OFF_HOURS",
        label="시간 외 사용",
        severity="medium",
        detect=detect_off_hours,
        requires=(KEY, CLASS, DATE, TIME),
        params={
            "night_start": "23", "night_end": "06",
            "check_weekend": True, "check_holiday": True, "check_night": True,
            "auto_holidays": True, "holidays": [], "holiday_exceptions": [], "enabled": True,
        },
    ),
    RuleTemplate(
        template="WATCH_MCC",
        label="주의 업종",
        severity="high",
        detect=detect_watch_mcc,
        requires=(KEY, CLASS, DATE, CATEGORY),
        params={
            "watch_mcc": [
                "상품권 전문판매",
                "볼 링 장",
                "영화관",
                "화   원",
                "기타회원제형태업소4",
                "자사카드발행백화점",
            ],
            "enabled": True,
        },
    ),
    RuleTemplate(
        template="SPLIT_PAYMENT",
        label="분할결제 의심",
        severity="medium",
        detect=detect_split_payment,
        requires=(KEY, CLASS, DATE, AMOUNT, CARD, MERCHANT, MERCHANT_BIZNO),
        params={
            "min_count": 2, "exclude_merchbizno": ["1018302925"],
            "min_total": 0, "window_minutes": 0, "enabled": True,
        },
    ),
]


@dataclass(frozen=True)
class Rule:
    code: str
    # The template this came from. Codes are source-specific so review keys
    # cannot collide, but the screen filters on the template — picking 고액 결제
    # must keep meaning the same thing after 점검대상 changes.
    template: str
    label: str
    severity: str
    detect: Callable[[List[Row], Dict[str, Any]], List[Finding]]
    params: Dict[str, Any]
    source: str
    required_columns: Tuple[str, ...]


def build_rules(sources: Dict[str, Source], templates: List[RuleTemplate]) -> List[Rule]:
    """Bind every template to each source that can supply the columns it needs."""
    rules = []
    for source in sources.values():
        for tpl in templates:
            if not source.has(*tpl.requires):
                continue
            code = f"{source.code_prefix}{tpl.template}"
            rules.append(
                Rule(
                    code=code,
                    template=tpl.template,
                    label=tpl.label,
                    severity=tpl.severity,
                    detect=tpl.detect,
                    params={
                        **tpl.params,
                        "columns": source.columns,
                        "code": code,
                        "severity": tpl.severity,
                    },
                    source=source.key,
                    required_columns=tuple(source.columns[k] for k in tpl.requires),
                )
            )
    return rules


RULES: List[Rule] = build_rules(SOURCES, TEMPLATES)


def rules_by_source(rules: List[Rule]) -> Dict[str, List[Rule]]:
    """Group rules by the source they read, preserving catalogue order."""
    grouped: Dict[str, List[Rule]] = defaultdict(list)
    for rule in rules:
        grouped[rule.source].append(rule)
    return dict(grouped)
