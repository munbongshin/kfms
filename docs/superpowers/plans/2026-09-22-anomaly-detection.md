# 법인카드 이상거래 탐지 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 법인카드 승인내역에서 감사 기준 위반 4종을 탐지하고, 담당자가 검토 상태를 남길 수 있는 전용 점검 화면을 만든다.

**Architecture:** 규칙은 백엔드 코드의 순수 함수로 둔다. 서비스가 `v_approval`을 한 번 읽어 모든 규칙에 같은 행 목록을 넘기고, 각 규칙이 `Finding` 목록을 반환한다. 검토 상태는 `kfms` DB에 저장하고 애플리케이션 계층에서 병합한다 (거래가 있는 `retail`과 크로스 조인 불가).

**Tech Stack:** FastAPI, SQLAlchemy 2.0 (async), PostgreSQL 16, pytest, Vue 3 + TypeScript + Element Plus + Pinia

**Spec:** `docs/superpowers/specs/2026-09-22-anomaly-detection-design.md`

## Global Constraints

- 모든 규칙은 `class = 'A'`(승인) 행만 대상으로 한다. `class = 'B'`는 원거래를 참조하는 취소 거래다.
- `finding_key = "{rule_code}:{subject}"`. 단건 규칙의 subject는 `seq`, 묶음 규칙은 `cardno|merchno|transdate`.
- `seq`는 NUMERIC이라 드라이버가 `Decimal`로 준다. 키에 쓸 때는 반드시 `str(int(seq))`로 정규화한다 — 그냥 `str()`하면 `"560348"`이 아니라 `"560348"`/`"560348.00"`처럼 환경에 따라 갈린다.
- `transdate`는 `CHAR(10)` 문자열(`"2023-07-31"`), `transtime`은 `CHAR(8)` 문자열(`"11:25:47"`). date/time 타입이 아니다.
- `apprtot`은 NUMERIC → `Decimal`. 금액 비교는 `Decimal`끼리 한다.
- `merchbizno`는 `CHAR(10)`이라 값이 짧으면 공백 패딩이 붙는다. 비교 전 `.strip()`한다.
- 신규 파이썬 모듈은 `backend/app/` 아래, 기존 `services/` · `db/repositories/` · `api/v1/` 구조를 따른다.

## 스펙과의 의도적 차이

스펙 "컴포넌트" 절은 규칙마다 자체 SELECT를 던지는 형태로 적혀 있다. 이 계획은 **규칙을 미리 읽어온 행에 대한 순수 함수**로 바꾼다.

- 스펙의 테스트 전략("실데이터가 아니라 픽스처로 경계를 찍는다")은 규칙이 SQL을 직접 실행하면 DB 없이는 불가능하다. 순수 함수면 픽스처 리스트만으로 테스트된다.
- 쿼리가 4번에서 1번으로 준다.
- 분할결제의 예외 처리는 SQL보다 파이썬 쪽이 읽기 쉽다.

한계: 전 행을 메모리에 올린다. 현재 200건에서는 문제없고, 수십만 건 규모가 되면 규칙별 SQL로 되돌려야 한다. 그때 `Finding` 인터페이스는 그대로 쓸 수 있다.

두 번째 차이로, 스펙의 PATCH 본문 예시에는 `fingerprint`가 없으나 이 계획은 **필수 필드로 받는다.** 서버가 저장 시점에 다시 계산하면 "담당자가 화면에서 본 것"이 아니라 "저장 순간의 상태"를 승인하게 되어, 조회와 클릭 사이에 데이터가 바뀌면 검토 의미가 어긋난다. 조회 응답에 지문을 실어 보내고 클라이언트가 그대로 돌려준다.

## 파일 구조

| 파일 | 책임 |
|---|---|
| `backend/app/anomaly/__init__.py` | 패키지 선언 |
| `backend/app/anomaly/models.py` | `Finding` — 탐지 건 표현, 키·지문 계산 |
| `backend/app/anomaly/rules.py` | `Rule` 정의와 규칙 4종, `RULES` 카탈로그 |
| `backend/app/db/repositories/anomaly.py` | `anomaly_review` 조회·upsert |
| `backend/app/services/anomaly_service.py` | 행 적재, 규칙 실행, 적용 가능 판정, 검토 병합 |
| `backend/app/api/v1/anomaly.py` | 엔드포인트 2종 |
| `backend/tests/anomaly/test_models.py` | 키·지문 |
| `backend/tests/anomaly/test_rules.py` | 규칙 경계값 |
| `frontend/src/stores/anomaly.ts` | 탐지 목록·검토 상태 |
| `frontend/src/views/AnomalyView.vue` | 점검 화면 |

수정 대상: `backend/app/db/models.py`, `backend/app/main.py`, `docker/init/01_schema.sql`, `backend/requirements.txt`, `frontend/src/services/api.ts`, `frontend/src/router/index.ts`, `frontend/src/components/layout/FunctionTabs.vue`

---

### Task 1: 테스트 기반과 Finding, 첫 규칙(HIGH_AMOUNT)

**Files:**
- Create: `backend/app/anomaly/__init__.py`, `backend/app/anomaly/models.py`, `backend/app/anomaly/rules.py`
- Create: `backend/tests/__init__.py` 확인, `backend/tests/anomaly/__init__.py`, `backend/tests/anomaly/test_models.py`, `backend/tests/anomaly/test_rules.py`
- Modify: `backend/requirements.txt`

**Interfaces:**
- Consumes: 없음 (첫 작업)
- Produces: `Finding` 데이터클래스(`finding_key`, `fingerprint` 프로퍼티), `Rule` 데이터클래스, `approvals(rows)` 헬퍼, `detect_high_amount(rows, params)`, `RULES` 목록

- [ ] **Step 1: pytest 의존성 추가**

`backend/requirements.txt` 끝에 추가:

```
pytest==8.3.4
pytest-asyncio==0.25.0
```

설치: `cd backend && pip install -r requirements.txt`

- [ ] **Step 2: 실패하는 테스트 작성**

`backend/tests/anomaly/__init__.py`를 빈 파일로 만들고, `backend/tests/anomaly/test_models.py`:

```python
from datetime import date
from decimal import Decimal

from app.anomaly.models import Finding


def _finding(**overrides):
    defaults = dict(
        rule_code="HIGH_AMOUNT",
        subject="560348",
        severity="high",
        summary="단건 5,850,000원",
        transactions=[{"seq": Decimal("560348"), "apprtot": Decimal("5850000.00")}],
        amount=Decimal("5850000.00"),
        occurred_on=date(2023, 7, 3),
    )
    defaults.update(overrides)
    return Finding(**defaults)


def test_finding_key_joins_rule_and_subject():
    assert _finding().finding_key == "HIGH_AMOUNT:560348"


def test_fingerprint_changes_when_a_transaction_is_added():
    one = _finding()
    two = _finding(
        transactions=[
            {"seq": Decimal("560348"), "apprtot": Decimal("5850000.00")},
            {"seq": Decimal("560349"), "apprtot": Decimal("1000.00")},
        ],
        amount=Decimal("5851000.00"),
    )
    assert one.fingerprint != two.fingerprint


def test_fingerprint_is_stable_for_the_same_content():
    assert _finding().fingerprint == _finding().fingerprint
```

- [ ] **Step 3: 실패 확인**

Run: `cd backend && python -m pytest tests/anomaly/test_models.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.anomaly'`

- [ ] **Step 4: Finding 구현**

`backend/app/anomaly/__init__.py`는 빈 파일. `backend/app/anomaly/models.py`:

```python
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
        # count and total surfaces a group that gained rows after review.
        raw = f"{len(self.transactions)}:{self.amount}"
        return sha256(raw.encode()).hexdigest()
```

- [ ] **Step 5: 통과 확인**

Run: `cd backend && python -m pytest tests/anomaly/test_models.py -v`
Expected: PASS (3 passed)

- [ ] **Step 6: HIGH_AMOUNT 실패 테스트 작성**

`backend/tests/anomaly/test_rules.py`:

```python
from decimal import Decimal

from app.anomaly.rules import detect_high_amount


def row(**overrides):
    defaults = dict(
        seq=Decimal("560348"),
        **{"class": "A"},
        cardno="4072855739182287",
        merchno="000049877848",
        merchbizno="1010497150",
        merchname="상패프로",
        mccname="일반한식",
        transdate="2023-07-31",
        transtime="11:25:47",
        apprtot=Decimal("100000.00"),
    )
    defaults.update(overrides)
    return defaults


def test_high_amount_flags_at_the_threshold():
    findings = detect_high_amount([row(apprtot=Decimal("500000"))], {"threshold": Decimal("500000")})
    assert len(findings) == 1
    assert findings[0].finding_key == "HIGH_AMOUNT:560348"


def test_high_amount_ignores_one_won_below_the_threshold():
    findings = detect_high_amount([row(apprtot=Decimal("499999"))], {"threshold": Decimal("500000")})
    assert findings == []


def test_high_amount_ignores_cancellations():
    cancelled = row(apprtot=Decimal("900000"), **{"class": "B"})
    assert detect_high_amount([cancelled], {"threshold": Decimal("500000")}) == []
```

- [ ] **Step 7: 실패 확인**

Run: `cd backend && python -m pytest tests/anomaly/test_rules.py -v`
Expected: FAIL — `ImportError: cannot import name 'detect_high_amount'`

- [ ] **Step 8: 규칙 뼈대와 HIGH_AMOUNT 구현**

`backend/app/anomaly/rules.py`:

```python
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
```

- [ ] **Step 9: 통과 확인**

Run: `cd backend && python -m pytest tests/anomaly -v`
Expected: PASS (6 passed)

- [ ] **Step 10: 커밋**

```bash
git add backend/requirements.txt backend/app/anomaly backend/tests/anomaly
git commit -m "Add anomaly rule scaffolding with the high-amount rule"
```

---

### Task 2: 시간 외 사용과 주의 업종 규칙

**Files:**
- Modify: `backend/app/anomaly/rules.py`
- Modify: `backend/tests/anomaly/test_rules.py`

**Interfaces:**
- Consumes: Task 1의 `Finding`, `Rule`, `approvals()`, `seq_key()`, `won()`, `row()` 테스트 헬퍼
- Produces: `detect_off_hours(rows, params)`, `detect_watch_mcc(rows, params)`, `RULES`에 두 항목 추가

- [ ] **Step 1: 실패 테스트 추가**

`backend/tests/anomaly/test_rules.py` 상단 import에 추가: `from app.anomaly.rules import detect_off_hours, detect_watch_mcc`

파일 끝에 추가:

```python
OFF_HOURS_PARAMS = {"night_start": "23", "night_end": "06"}


def test_off_hours_flags_saturday():
    # 2023-07-29 is a Saturday.
    findings = detect_off_hours([row(transdate="2023-07-29", transtime="14:30:00")], OFF_HOURS_PARAMS)
    assert len(findings) == 1
    assert "토요일" in findings[0].summary


def test_off_hours_ignores_a_weekday_daytime_payment():
    # 2023-07-28 is a Friday.
    assert detect_off_hours([row(transdate="2023-07-28", transtime="14:30:00")], OFF_HOURS_PARAMS) == []


def test_off_hours_boundary_2259_is_not_night():
    assert detect_off_hours([row(transdate="2023-07-28", transtime="22:59:59")], OFF_HOURS_PARAMS) == []


def test_off_hours_boundary_2300_is_night():
    assert len(detect_off_hours([row(transdate="2023-07-28", transtime="23:00:00")], OFF_HOURS_PARAMS)) == 1


def test_off_hours_boundary_0559_is_night():
    assert len(detect_off_hours([row(transdate="2023-07-28", transtime="05:59:59")], OFF_HOURS_PARAMS)) == 1


def test_off_hours_boundary_0600_is_not_night():
    assert detect_off_hours([row(transdate="2023-07-28", transtime="06:00:00")], OFF_HOURS_PARAMS) == []


def test_off_hours_ignores_cancellations():
    cancelled = row(transdate="2023-07-29", transtime="14:30:00", **{"class": "B"})
    assert detect_off_hours([cancelled], OFF_HOURS_PARAMS) == []


WATCH_PARAMS = {"watch_mcc": ["상품권 전문판매", "영화관"]}


def test_watch_mcc_flags_a_listed_category():
    findings = detect_watch_mcc([row(mccname="상품권 전문판매")], WATCH_PARAMS)
    assert len(findings) == 1
    assert findings[0].summary == "주의 업종: 상품권 전문판매"


def test_watch_mcc_ignores_an_unlisted_category():
    assert detect_watch_mcc([row(mccname="일반한식")], WATCH_PARAMS) == []


def test_watch_mcc_ignores_null_category():
    # 43 of 190 approvals have no mccname; they must not raise.
    assert detect_watch_mcc([row(mccname=None)], WATCH_PARAMS) == []


def test_watch_mcc_ignores_cancellations():
    cancelled = row(mccname="영화관", **{"class": "B"})
    assert detect_watch_mcc([cancelled], WATCH_PARAMS) == []
```

- [ ] **Step 2: 실패 확인**

Run: `cd backend && python -m pytest tests/anomaly/test_rules.py -v`
Expected: FAIL — `ImportError: cannot import name 'detect_off_hours'`

- [ ] **Step 3: 두 규칙 구현**

`backend/app/anomaly/rules.py`의 `RULES` 정의 **위에** 추가:

```python
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
                amount=r["apprtot"] or Decimal("0"),
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
                amount=r["apprtot"] or Decimal("0"),
                occurred_on=date.fromisoformat(r["transdate"]),
            )
        )
    return findings
```

`RULES` 목록에 두 항목 추가:

```python
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
```

`watch_mcc` 값의 내부 공백은 DB 실제 값 그대로다. 임의로 정규화하면 매칭되지 않는다.

- [ ] **Step 4: 통과 확인**

Run: `cd backend && python -m pytest tests/anomaly -v`
Expected: PASS (17 passed)

- [ ] **Step 5: 커밋**

```bash
git add backend/app/anomaly/rules.py backend/tests/anomaly/test_rules.py
git commit -m "Add off-hours and watch-category anomaly rules"
```

---

### Task 3: 분할결제 규칙

**Files:**
- Modify: `backend/app/anomaly/rules.py`
- Modify: `backend/tests/anomaly/test_rules.py`

**Interfaces:**
- Consumes: Task 1·2의 `Finding`, `Rule`, `approvals()`, `won()`
- Produces: `detect_split_payment(rows, params)`, `RULES`에 항목 추가. subject 형식은 `"{cardno}|{merchno}|{transdate}"`

- [ ] **Step 1: 실패 테스트 추가**

import에 `detect_split_payment` 추가 후 파일 끝에:

```python
SPLIT_PARAMS = {"min_count": 2, "exclude_merchbizno": ["1018302925"]}


def test_split_payment_flags_two_payments_at_one_merchant_on_one_day():
    rows = [
        row(seq=Decimal("1"), apprtot=Decimal("100000")),
        row(seq=Decimal("2"), apprtot=Decimal("104000")),
    ]
    findings = detect_split_payment(rows, SPLIT_PARAMS)
    assert len(findings) == 1
    assert findings[0].finding_key == "SPLIT_PAYMENT:4072855739182287|000049877848|2023-07-31"
    assert findings[0].amount == Decimal("204000")
    assert "2건" in findings[0].summary


def test_split_payment_ignores_a_single_payment():
    assert detect_split_payment([row()], SPLIT_PARAMS) == []


def test_split_payment_does_not_group_across_merchants():
    rows = [
        row(seq=Decimal("1"), merchno="AAA"),
        row(seq=Decimal("2"), merchno="BBB"),
    ]
    assert detect_split_payment(rows, SPLIT_PARAMS) == []


def test_split_payment_does_not_group_across_days():
    rows = [
        row(seq=Decimal("1"), transdate="2023-07-30"),
        row(seq=Decimal("2"), transdate="2023-07-31"),
    ]
    assert detect_split_payment(rows, SPLIT_PARAMS) == []


def test_split_payment_skips_excluded_business_numbers():
    # 우정사업본부: 41 of 200 rows, repeated postage is legitimate.
    rows = [
        row(seq=Decimal("1"), merchbizno="1018302925"),
        row(seq=Decimal("2"), merchbizno="1018302925"),
    ]
    assert detect_split_payment(rows, SPLIT_PARAMS) == []


def test_split_payment_strips_padded_business_numbers():
    # merchbizno is CHAR(10), so shorter values arrive space-padded.
    rows = [
        row(seq=Decimal("1"), merchbizno="1018302925"),
        row(seq=Decimal("2"), merchbizno="1018302925 "),
    ]
    assert detect_split_payment(rows, SPLIT_PARAMS) == []


def test_split_payment_ignores_cancellations():
    rows = [
        row(seq=Decimal("1")),
        row(seq=Decimal("2"), **{"class": "B"}),
    ]
    assert detect_split_payment(rows, SPLIT_PARAMS) == []
```

- [ ] **Step 2: 실패 확인**

Run: `cd backend && python -m pytest tests/anomaly/test_rules.py -v`
Expected: FAIL — `ImportError: cannot import name 'detect_split_payment'`

- [ ] **Step 3: 구현**

`rules.py`의 `RULES` 위에 추가 (`from collections import defaultdict`를 상단 import에 추가):

```python
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
        total = sum((m["apprtot"] or Decimal("0") for m in members), Decimal("0"))
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
```

`RULES`에 추가:

```python
    Rule(
        code="SPLIT_PAYMENT",
        label="분할결제 의심",
        severity="medium",
        detect=detect_split_payment,
        params={"min_count": 2, "exclude_merchbizno": ["1018302925"]},
        required_columns=("seq", "class", "cardno", "merchno", "merchbizno", "transdate", "apprtot"),
    ),
```

- [ ] **Step 4: 통과 확인**

Run: `cd backend && python -m pytest tests/anomaly -v`
Expected: PASS (24 passed)

- [ ] **Step 5: 커밋**

```bash
git add backend/app/anomaly/rules.py backend/tests/anomaly/test_rules.py
git commit -m "Add split-payment anomaly rule with merchant exclusions"
```

---

### Task 4: 검토 상태 테이블과 저장소

**Files:**
- Modify: `docker/init/01_schema.sql`, `backend/app/db/models.py`
- Create: `backend/app/db/repositories/anomaly.py`

**Interfaces:**
- Consumes: 없음
- Produces: `AnomalyReview` ORM 모델, `AnomalyRepository(session)` with `async get_reviews(database_id, finding_keys) -> Dict[str, AnomalyReview]` and `async upsert_review(database_id, finding_key, rule_code, status, fingerprint, note) -> AnomalyReview`

- [ ] **Step 1: 스키마 정의 추가**

`docker/init/01_schema.sql`의 `query_history` 블록 뒤에 추가:

```sql
CREATE TABLE anomaly_review (
    id           SERIAL PRIMARY KEY,
    database_id  VARCHAR(255) NOT NULL,
    finding_key  VARCHAR(200) NOT NULL,
    rule_code    VARCHAR(40)  NOT NULL,
    status       VARCHAR(20)  NOT NULL,
    fingerprint  VARCHAR(64)  NOT NULL,
    note         TEXT,
    reviewed_at  TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (database_id, finding_key)
);

CREATE INDEX idx_anomaly_review_lookup ON anomaly_review(database_id, rule_code);
```

- [ ] **Step 2: 운영 DB에 반영**

init 스크립트는 기존 볼륨에서 재실행되지 않으므로 직접 적용한다.

```bash
docker exec -i kfms-postgres psql -U postgres -d kfms <<'SQL'
CREATE TABLE IF NOT EXISTS anomaly_review (
    id           SERIAL PRIMARY KEY,
    database_id  VARCHAR(255) NOT NULL,
    finding_key  VARCHAR(200) NOT NULL,
    rule_code    VARCHAR(40)  NOT NULL,
    status       VARCHAR(20)  NOT NULL,
    fingerprint  VARCHAR(64)  NOT NULL,
    note         TEXT,
    reviewed_at  TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (database_id, finding_key)
);
CREATE INDEX IF NOT EXISTS idx_anomaly_review_lookup ON anomaly_review(database_id, rule_code);
SQL
```

확인: `docker exec kfms-postgres psql -U postgres -d kfms -c "\d anomaly_review"`
Expected: 8개 컬럼과 UNIQUE 제약이 출력된다.

- [ ] **Step 3: ORM 모델 추가**

`backend/app/db/models.py` 끝에 추가 (`UniqueConstraint`를 sqlalchemy import에 추가):

```python
class AnomalyReview(Base):
    """Reviewer's decision on one anomaly finding."""

    __tablename__ = "anomaly_review"
    __table_args__ = (UniqueConstraint("database_id", "finding_key"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    database_id: Mapped[str] = mapped_column(String(255), nullable=False)
    finding_key: Mapped[str] = mapped_column(String(200), nullable=False)
    rule_code: Mapped[str] = mapped_column(String(40), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, comment="confirmed or dismissed")
    fingerprint: Mapped[str] = mapped_column(
        String(64), nullable=False, comment="Finding content when reviewed; a mismatch reopens it"
    )
    note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    reviewed_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
```

- [ ] **Step 4: 저장소 구현**

`backend/app/db/repositories/anomaly.py`:

```python
"""Repository for anomaly_review."""
from typing import Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import AnomalyReview


class AnomalyRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_reviews(
        self, database_id: str, finding_keys: List[str]
    ) -> Dict[str, AnomalyReview]:
        """Reviews for the given keys, indexed by finding_key."""
        if not finding_keys:
            return {}

        result = await self.session.execute(
            select(AnomalyReview).where(
                AnomalyReview.database_id == database_id,
                AnomalyReview.finding_key.in_(finding_keys),
            )
        )
        return {r.finding_key: r for r in result.scalars().all()}

    async def upsert_review(
        self,
        database_id: str,
        finding_key: str,
        rule_code: str,
        status: str,
        fingerprint: str,
        note: Optional[str] = None,
    ) -> AnomalyReview:
        result = await self.session.execute(
            select(AnomalyReview).where(
                AnomalyReview.database_id == database_id,
                AnomalyReview.finding_key == finding_key,
            )
        )
        review = result.scalar_one_or_none()

        if review is None:
            review = AnomalyReview(
                database_id=database_id,
                finding_key=finding_key,
                rule_code=rule_code,
                status=status,
                fingerprint=fingerprint,
                note=note,
            )
            self.session.add(review)
        else:
            review.status = status
            review.fingerprint = fingerprint
            review.note = note

        await self.session.commit()
        await self.session.refresh(review)
        return review
```

- [ ] **Step 5: 임포트 확인**

Run: `cd backend && python -c "from app.db.repositories.anomaly import AnomalyRepository; from app.db.models import AnomalyReview; print('ok')"`
Expected: `ok`

- [ ] **Step 6: 커밋**

```bash
git add docker/init/01_schema.sql backend/app/db/models.py backend/app/db/repositories/anomaly.py
git commit -m "Store reviewer decisions on anomaly findings"
```

---

### Task 5: 탐지 서비스

**Files:**
- Create: `backend/app/services/anomaly_service.py`
- Create: `backend/tests/anomaly/test_service.py`

**Interfaces:**
- Consumes: Task 1~3의 `RULES`, `Finding`; Task 4의 `AnomalyRepository`
- Produces: `AnomalyService(pool, repo)` with `async list_findings(database_id, rule_code=None, status=None) -> dict`. 반환 형태는 `{"applicable_rules": [...], "findings": [...]}`. 병합 헬퍼 `merge_reviews(findings, reviews)`는 모듈 수준 순수 함수로 두어 테스트한다.

- [ ] **Step 1: 실패 테스트 작성**

`backend/tests/anomaly/test_service.py`:

```python
from datetime import date, datetime, timezone
from decimal import Decimal

from app.anomaly.models import Finding
from app.services.anomaly_service import merge_reviews


class FakeReview:
    def __init__(self, status, fingerprint, note=None):
        self.status = status
        self.fingerprint = fingerprint
        self.note = note
        self.reviewed_at = datetime(2026, 9, 22, tzinfo=timezone.utc)


def finding(**overrides):
    defaults = dict(
        rule_code="SPLIT_PAYMENT",
        subject="CARD|MERCH|2023-07-31",
        severity="medium",
        summary="동일 가맹점 당일 2건 204,000원",
        transactions=[{"seq": Decimal("1")}, {"seq": Decimal("2")}],
        amount=Decimal("204000"),
        occurred_on=date(2023, 7, 31),
    )
    defaults.update(overrides)
    return Finding(**defaults)


def test_unreviewed_finding_has_no_review_and_is_not_stale():
    merged = merge_reviews([finding()], {})
    assert merged[0]["review"] is None
    assert merged[0]["stale"] is False


def test_review_with_matching_fingerprint_is_not_stale():
    f = finding()
    merged = merge_reviews([f], {f.finding_key: FakeReview("dismissed", f.fingerprint)})
    assert merged[0]["review"]["status"] == "dismissed"
    assert merged[0]["stale"] is False


def test_review_goes_stale_when_the_group_grows():
    reviewed = finding()
    grown = finding(
        transactions=[{"seq": Decimal("1")}, {"seq": Decimal("2")}, {"seq": Decimal("3")}],
        amount=Decimal("304000"),
    )
    merged = merge_reviews([grown], {reviewed.finding_key: FakeReview("dismissed", reviewed.fingerprint)})
    assert merged[0]["stale"] is True
```

- [ ] **Step 2: 실패 확인**

Run: `cd backend && python -m pytest tests/anomaly/test_service.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.services.anomaly_service'`

- [ ] **Step 3: 서비스 구현**

`backend/app/services/anomaly_service.py`:

```python
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
```

- [ ] **Step 4: 통과 확인**

Run: `cd backend && python -m pytest tests/anomaly -v`
Expected: PASS (27 passed)

- [ ] **Step 5: 커밋**

```bash
git add backend/app/services/anomaly_service.py backend/tests/anomaly/test_service.py
git commit -m "Run anomaly rules and merge reviewer decisions"
```

---

### Task 6: API 엔드포인트

**Files:**
- Create: `backend/app/api/v1/anomaly.py`
- Modify: `backend/app/main.py:16,120`

**Interfaces:**
- Consumes: Task 5의 `AnomalyService`, Task 4의 `AnomalyRepository`
- Produces: `GET /api/v1/anomaly/findings`, `PATCH /api/v1/anomaly/findings/{finding_key}/review`

- [ ] **Step 1: 라우터 작성**

`backend/app/api/v1/anomaly.py`:

```python
"""Anomaly detection endpoints."""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status as http_status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.anomaly.rules import RULES
from app.db.repositories.anomaly import AnomalyRepository
from app.dependencies import get_db, get_db_pool
from app.services.anomaly_service import AnomalyService

router = APIRouter(prefix="/anomaly", tags=["Anomaly"])


def get_anomaly_service(
    db: AsyncSession = Depends(get_db),
    pool=Depends(get_db_pool),
) -> AnomalyService:
    return AnomalyService(pool, AnomalyRepository(db))


class ReviewRequest(BaseModel):
    database_id: str
    status: str
    fingerprint: str
    note: Optional[str] = None


@router.get("/findings")
async def list_findings(
    database_id: str = Query(...),
    rule_code: Optional[str] = None,
    status: Optional[str] = None,
    service: AnomalyService = Depends(get_anomaly_service),
):
    """Findings for one connection, with review state merged in."""
    return await service.list_findings(database_id, rule_code=rule_code, status=status)


@router.patch("/findings/{finding_key:path}/review")
async def review_finding(
    finding_key: str,
    request: ReviewRequest,
    db: AsyncSession = Depends(get_db),
):
    if request.status not in ("confirmed", "dismissed"):
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail="status must be 'confirmed' or 'dismissed'",
        )

    rule_code = finding_key.split(":", 1)[0]
    if rule_code not in {r.code for r in RULES}:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown rule in finding_key: {rule_code}",
        )

    review = await AnomalyRepository(db).upsert_review(
        database_id=request.database_id,
        finding_key=finding_key,
        rule_code=rule_code,
        status=request.status,
        fingerprint=request.fingerprint,
        note=request.note,
    )

    return {
        "finding_key": review.finding_key,
        "status": review.status,
        "note": review.note,
        "reviewed_at": review.reviewed_at.isoformat(),
    }
```

`finding_key`에 `|`와 `:`가 들어가므로 경로 변환자 `:path`가 필요하다. 없으면 분할결제 키가 404가 된다.

- [ ] **Step 2: 라우터 등록**

`backend/app/main.py:16`을 수정:

```python
from app.api.v1 import databases, query, excel, history, anomaly
```

`backend/app/main.py:120` 뒤에 추가:

```python
app.include_router(anomaly.router, prefix="/api/v1")
```

- [ ] **Step 3: 서버 기동 확인**

백엔드는 `--reload`로 떠 있다. 다음으로 확인:

Run:
```bash
curl -s "http://127.0.0.1:8000/api/v1/anomaly/findings?database_id=1" | python -m json.tool | head -40
```
Expected: `applicable_rules` 4건이 `applicable: true`로 나오고, `findings`에 탐지 건이 담긴다. `WATCH_MCC`에는 `caveat`로 미분류 건수가 붙는다.

- [ ] **Step 4: 기준선 대조**

Run:
```bash
curl -s "http://127.0.0.1:8000/api/v1/anomaly/findings?database_id=1" \
  | python -c "import json,sys,collections; d=json.load(sys.stdin); print(collections.Counter(f['rule_code'] for f in d['findings']))"
```
Expected: `OFF_HOURS 3`, `HIGH_AMOUNT 5`, `WATCH_MCC 5`, `SPLIT_PAYMENT 5`

스펙의 기준선과 다르면 규칙 구현을 점검한다. 숫자가 다를 때 규칙이 아니라 기준선이 틀렸다고 단정하지 말 것 — 기준선은 2026-09-22 실측값이다.

- [ ] **Step 5: 검토 저장 왕복 확인**

Run:
```bash
cd backend && python - <<'PY'
import json, urllib.parse, urllib.request
B = "http://127.0.0.1:8000/api/v1/anomaly"

def get():
    return json.loads(urllib.request.urlopen(f"{B}/findings?database_id=1").read())

first = get()["findings"][0]
body = json.dumps({
    "database_id": "1",
    "status": "dismissed",
    "fingerprint": first["fingerprint"],
    "note": "확인 완료",
}).encode()
key = urllib.parse.quote(first["finding_key"], safe="")
req = urllib.request.Request(f"{B}/findings/{key}/review", data=body,
                             headers={"Content-Type": "application/json"}, method="PATCH")
print("PATCH ->", json.loads(urllib.request.urlopen(req).read()))

after = next(f for f in get()["findings"] if f["finding_key"] == first["finding_key"])
print("review:", after["review"], "| stale:", after["stale"])
PY
```
Expected: `PATCH -> {'status': 'dismissed', ...}` 에 이어 `review: {'status': 'dismissed', ...} | stale: False`

`stale`이 `True`로 나오면 조회와 저장 사이에 지문이 어긋난 것이다. `merge_reviews`가 내보내는 `fingerprint`가 `Finding.fingerprint`와 같은 값인지 확인한다.

`finding_key`의 `|`와 `:`는 반드시 URL 인코딩해서 보낸다.

- [ ] **Step 6: 커밋**

```bash
git add backend/app/api/v1/anomaly.py backend/app/main.py
git commit -m "Expose anomaly findings and review endpoints"
```

---

### Task 7: 점검 화면

**Files:**
- Create: `frontend/src/stores/anomaly.ts`, `frontend/src/views/AnomalyView.vue`
- Modify: `frontend/src/services/api.ts`, `frontend/src/router/index.ts`, `frontend/src/components/layout/FunctionTabs.vue`

**Interfaces:**
- Consumes: Task 6의 엔드포인트
- Produces: `/anomaly` 라우트, 좌측 "점검" 탭

- [ ] **Step 1: API 클라이언트 추가**

`frontend/src/services/api.ts`의 `history` 블록 뒤, 객체 닫기 전에 추가:

```typescript
  // Anomaly detection
  anomaly: {
    async listFindings(params: {
      database_id: string
      rule_code?: string
      status?: string
    }) {
      const response = await apiClient.get('/anomaly/findings', { params })
      return response.data
    },

    async review(findingKey: string, data: {
      database_id: string
      status: 'confirmed' | 'dismissed'
      fingerprint: string
      note?: string
    }) {
      const response = await apiClient.patch(
        `/anomaly/findings/${encodeURIComponent(findingKey)}/review`,
        data
      )
      return response.data
    },
  },
```

`encodeURIComponent`가 필요하다. 분할결제 키의 `|`가 그대로 나가면 URL이 깨진다.

- [ ] **Step 2: 스토어 작성**

`frontend/src/stores/anomaly.ts`:

```typescript
/**
 * Anomaly Store (Pinia)
 * Findings for the active connection plus reviewer actions.
 */
import { defineStore } from 'pinia'
import { ref } from 'vue'
import { ElMessage } from 'element-plus'
import { api } from '../services/api'

export interface RuleStatus {
  rule_code: string
  label: string
  applicable: boolean
  caveat?: string
}

export interface FindingReview {
  status: 'confirmed' | 'dismissed'
  note: string | null
  reviewed_at: string
}

export interface Finding {
  finding_key: string
  rule_code: string
  severity: 'high' | 'medium' | 'low'
  summary: string
  amount: number
  occurred_on: string
  transactions: any[]
  fingerprint: string
  review: FindingReview | null
  stale: boolean
}

export const useAnomalyStore = defineStore('anomaly', () => {
  const rules = ref<RuleStatus[]>([])
  const findings = ref<Finding[]>([])
  const loading = ref(false)
  const ruleFilter = ref('')
  const statusFilter = ref('')

  async function fetchFindings(databaseId: string) {
    loading.value = true
    try {
      const data = await api.anomaly.listFindings({
        database_id: databaseId,
        rule_code: ruleFilter.value || undefined,
        status: statusFilter.value || undefined,
      })
      rules.value = data.applicable_rules
      findings.value = data.findings
    } catch (error) {
      ElMessage.error('점검 결과를 불러오지 못했습니다')
    } finally {
      loading.value = false
    }
  }

  async function review(
    databaseId: string,
    finding: Finding,
    status: 'confirmed' | 'dismissed'
  ) {
    try {
      const updated = await api.anomaly.review(finding.finding_key, {
        database_id: databaseId,
        status,
        // The fingerprint the reviewer actually saw, so a later change reopens it.
        fingerprint: finding.fingerprint,
      })
      finding.review = {
        status: updated.status,
        note: updated.note,
        reviewed_at: updated.reviewed_at,
      }
      finding.stale = false
      ElMessage.success(status === 'confirmed' ? '확인 처리했습니다' : '정상으로 표시했습니다')
    } catch (error) {
      ElMessage.error('검토 상태를 저장하지 못했습니다')
    }
  }

  return { rules, findings, loading, ruleFilter, statusFilter, fetchFindings, review }
})
```

지문은 Task 5의 서버 응답에 담겨 온 값을 그대로 돌려보낸다. 프론트에서 다시 계산하면 `Decimal` → `number` 변환 차이로 어긋나고, 그러면 모든 건이 영구히 `stale`로 뜬다.

- [ ] **Step 3: 화면 작성**

`frontend/src/views/AnomalyView.vue`:

```vue
<template>
  <div class="anomaly-view">
    <el-card>
      <template #header>
        <div class="header">
          <span>이상거래 점검</span>
          <el-button :loading="store.loading" @click="refresh">
            <el-icon><Refresh /></el-icon>
            다시 검사
          </el-button>
        </div>
      </template>

      <el-alert
        v-if="!databaseStore.activeConnectionId"
        type="info"
        :closable="false"
        show-icon
        title="먼저 좌측에서 데이터베이스 연결을 선택하세요"
      />

      <template v-else>
        <div class="rules">
          <el-tag
            v-for="rule in store.rules"
            :key="rule.rule_code"
            :type="rule.applicable ? 'success' : 'info'"
            :effect="rule.applicable ? 'light' : 'plain'"
            class="rule-tag"
          >
            {{ rule.label }}<span v-if="rule.caveat"> — {{ rule.caveat }}</span>
          </el-tag>
        </div>

        <div class="filters">
          <el-select v-model="store.ruleFilter" placeholder="전체 규칙" clearable style="width: 180px">
            <el-option v-for="r in store.rules" :key="r.rule_code" :label="r.label" :value="r.rule_code" />
          </el-select>
          <el-select v-model="store.statusFilter" placeholder="전체 상태" clearable style="width: 160px">
            <el-option label="미검토" value="unreviewed" />
            <el-option label="확인함" value="confirmed" />
            <el-option label="정상" value="dismissed" />
          </el-select>
          <el-button @click="refresh">적용</el-button>
        </div>

        <el-table :data="store.findings" v-loading="store.loading" stripe style="width: 100%">
          <el-table-column label="심각도" width="90">
            <template #default="{ row }">
              <el-tag :type="severityType(row.severity)" size="small">{{ row.severity }}</el-tag>
            </template>
          </el-table-column>

          <el-table-column prop="occurred_on" label="거래일" width="120" />

          <el-table-column label="사유" min-width="280">
            <template #default="{ row }">
              {{ row.summary }}
              <el-tag v-if="row.stale" type="warning" size="small" class="stale">검토 후 변경됨</el-tag>
            </template>
          </el-table-column>

          <el-table-column label="금액" width="140" align="right">
            <template #default="{ row }">{{ row.amount.toLocaleString() }}</template>
          </el-table-column>

          <el-table-column label="건수" width="80" align="right">
            <template #default="{ row }">{{ row.transactions.length }}</template>
          </el-table-column>

          <el-table-column label="검토" width="200" fixed="right">
            <template #default="{ row }">
              <el-button-group v-if="!row.review || row.stale">
                <el-button size="small" @click="store.review(connectionId, row, 'confirmed')">확인</el-button>
                <el-button size="small" @click="store.review(connectionId, row, 'dismissed')">정상</el-button>
              </el-button-group>
              <el-tag v-else :type="row.review.status === 'dismissed' ? 'info' : 'success'" size="small">
                {{ row.review.status === 'dismissed' ? '정상' : '확인함' }}
              </el-tag>
            </template>
          </el-table-column>
        </el-table>

        <el-empty v-if="!store.loading && store.findings.length === 0" description="탐지된 건이 없습니다" />
      </template>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, watch } from 'vue'
import { Refresh } from '@element-plus/icons-vue'
import { useAnomalyStore } from '../stores/anomaly'
import { useDatabaseStore } from '../stores/database'

const store = useAnomalyStore()
const databaseStore = useDatabaseStore()

const connectionId = computed(() => String(databaseStore.activeConnectionId ?? ''))

function severityType(severity: string) {
  return severity === 'high' ? 'danger' : severity === 'medium' ? 'warning' : 'info'
}

function refresh() {
  if (connectionId.value) store.fetchFindings(connectionId.value)
}

watch(connectionId, refresh)
onMounted(refresh)
</script>

<style scoped>
.header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.rules {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 16px;
}

.filters {
  display: flex;
  gap: 10px;
  margin-bottom: 16px;
}

.stale {
  margin-left: 8px;
}
</style>
```

- [ ] **Step 4: 라우트와 탭 등록**

`frontend/src/router/index.ts`의 `routes` 배열, `history` 항목 뒤에 추가:

```typescript
  ,{
    path: '/anomaly',
    name: 'anomaly',
    component: () => import('../views/AnomalyView.vue'),
    meta: { title: 'Anomaly' }
  }
```

`frontend/src/components/layout/FunctionTabs.vue`의 import를 수정:

```typescript
import { ChatLineSquare, Coin, Clock, Warning } from '@element-plus/icons-vue'
```

`tabs` 배열에 추가:

```typescript
  { name: 'anomaly', label: '점검', icon: Warning },
```

- [ ] **Step 5: 타입 체크**

Run: `cd frontend && npx vue-tsc --noEmit`
Expected: 오류 없음 (종료 코드 0)

- [ ] **Step 6: 브라우저 확인**

개발 서버를 띄우고 (`cd frontend && npm run dev`) 좌측 "점검" 탭을 연다.

확인 항목:
1. 규칙 4개가 태그로 표시되고 `WATCH_MCC`에 미분류 건수 주의문구가 붙는다
2. 목록에 탐지 건이 심각도 순으로 나온다
3. "정상" 버튼을 누르면 해당 행이 `정상` 태그로 바뀐다
4. 새로고침해도 그 상태가 유지된다
5. 규칙·상태 필터가 동작한다

- [ ] **Step 7: 커밋**

```bash
git add frontend/src/stores/anomaly.ts frontend/src/views/AnomalyView.vue \
        frontend/src/services/api.ts frontend/src/router/index.ts \
        frontend/src/components/layout/FunctionTabs.vue \
        backend/app/services/anomaly_service.py
git commit -m "Add the anomaly review screen"
```
