# 법인카드 이상거래 탐지

**날짜:** 2026-09-22
**상태:** 승인됨 (구현 대기)
**범위:** 백엔드 규칙 엔진 + 검토 상태 저장 + 전용 점검 화면. 기존 질의/이력 흐름은 건드리지 않는다.

## 문제

법인카드 승인내역에서 "평소와 다른 비정상 거래"를 찾고 싶으나, 현재는 담당자가 질의 화면에서 매번 SQL을 생성해 눈으로 훑는 것 외에 방법이 없다. 점검 기준이 사람 머릿속에 있어 누락되고, 같은 점검을 반복할 때마다 결과가 달라진다.

## 데이터 제약 (설계의 전제)

구현 전 실측한 내용이다. 이 제약이 접근 방식을 결정했다.

| 항목 | 실측값 |
|---|---|
| 승인내역 건수 | 200건 (`v_approval`) |
| 기간 | 2023-06-12 ~ 2023-07-31 (7주) |
| 카드 수 | 100장 |
| 카드당 거래 | 대부분 1~3건 |
| 업종 미분류 | 47건 (23%) — 취소건 제외 시 43건 |

**카드별 통계 기준선이 성립하지 않는다.** 카드당 거래가 1~3건이라 "이 카드의 평소 패턴 대비 이상"을 계산하면 거의 전부 오탐이 된다. 따라서 1차는 규칙 기반으로 한다. 통계 탐지는 데이터가 쌓인 뒤 같은 `Finding` 인터페이스로 규칙을 추가하는 형태로 얹는다.

**DB가 분리되어 있다.** 거래는 `retail`, 앱 상태는 `kfms`에 있고 크로스 조인이 불가능하다. 탐지는 `retail`에서, 검토 상태는 `kfms`에 저장하고 애플리케이션 계층에서 병합한다.

## 결정 사항

브레인스토밍에서 확정된 선택과 근거.

| 결정 | 선택 | 근거 |
|---|---|---|
| 탐지 방식 | **규칙 기반 먼저**, 통계는 확장 여지만 | 7주·카드당 1~3건으로는 통계 기준선이 없음 |
| 규칙 위치 | **백엔드 코드** (뷰 아님) | 임계값 조정이 DDL 변경이 되지 않게. 예외 관리가 SQL보다 코드가 깔끔 |
| 결과 노출 | **전용 점검 화면** | 정기 점검 용도. LLM을 거치지 않아 결과가 항상 동일 |
| 상태 저장 | **검토 처리 저장** | 상시 오탐을 담당자가 걸러낼 수 있어야 함 |
| 탐지 대상 | **`class='A'`만** | `class='B'` 10건은 전부 `origintransdate`/`originapprno`가 채워진 취소 거래. 포함하면 고액·분할 집계가 부풀려짐 |
| 중복 표시 | **규칙별 개별 탐지 건** | 감사는 사유별 근거가 필요. `finding_key`도 규칙 단위라 일관됨 |

## 탐지 건 식별

검토 상태("확인함")를 저장하려면 탐지 건에 재실행 간 안정적인 키가 필요하다. 규칙 성격이 둘로 갈린다.

- **단건 규칙** (`OFF_HOURS`, `HIGH_AMOUNT`, `WATCH_MCC`) — 대상이 거래 1건. 주체는 `seq`
- **묶음 규칙** (`SPLIT_PAYMENT`) — 대상이 여러 거래. 주체는 `cardno|merchno|transdate`

```
finding_key = "{rule_code}:{subject}"
```

`seq`는 `v_approval` 200건 전부 고유하고 NULL이 없어 식별자로 적합하다. (`cardno+apprno+transdate`는 취소쌍 때문에 194개로 중복되므로 쓰지 않는다.)

### 지문 (검토 후 변경 감지)

묶음 규칙은 나중에 거래가 더 붙어도 `finding_key`가 같다. 2건짜리를 "정상임"으로 처리한 뒤 3건이 되면 **승인이 새 거래까지 조용히 덮는다.** 감사 도구에서 이는 결함이다.

검토 시점의 지문(대상 거래 건수 + 금액 합계의 해시)을 함께 저장하고, 재조회 시 지문이 다르면 `stale=true`로 표시해 다시 검토 대상에 올린다.

## 데이터 모델

`kfms` DB에 테이블 하나를 추가한다. `docker/init/01_schema.sql`에 정의를 넣고, 운영 중인 DB에는 `ALTER`로 반영한다 (init 스크립트는 기존 볼륨에서 재실행되지 않음).

```sql
CREATE TABLE anomaly_review (
    id           SERIAL PRIMARY KEY,
    database_id  VARCHAR(255) NOT NULL,
    finding_key  VARCHAR(200) NOT NULL,
    rule_code    VARCHAR(40)  NOT NULL,
    status       VARCHAR(20)  NOT NULL,   -- 'confirmed' | 'dismissed'
    fingerprint  VARCHAR(64)  NOT NULL,
    note         TEXT,
    reviewed_at  TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (database_id, finding_key)
);

CREATE INDEX idx_anomaly_review_lookup ON anomaly_review(database_id, rule_code);
```

`database_id`로 범위를 나누는 이유는 앱이 여러 연결을 지원하기 때문이다. 연결이 다르면 같은 `seq`가 다른 거래를 가리킨다.

규칙 자체는 테이블이 아니라 **코드의 카탈로그**다. 규칙 추가가 마이그레이션이 되지 않게 한다.

## 규칙 카탈로그

모든 규칙은 `class='A'`만 대상으로 한다. 괄호 안은 2026-09-22 기준 현재 데이터 적중 수이며, 구현 후 수동 확인용 기준선이다 (테스트 기대값으로 쓰지 않는다).

### `OFF_HOURS` — 시간 외 사용 (3건)

토요일·일요일 거래, 또는 `transtime`이 심야 구간인 거래.

- 파라미터: `night_start = "23"`, `night_end = "06"` (23:00~05:59)
- 주말 3건 적중. 심야는 현재 0건이나 규정상 필수이며 데이터가 늘면 동작한다
- `summary` 예: `"토요일 14:30 결제"`

### `SPLIT_PAYMENT` — 분할결제 의심 (5건)

동일 `cardno` + `merchno` + `transdate`에 승인 2건 이상.

- 파라미터: `min_count = 2`, `exclude_merchbizno = ["1018302925"]`
- 예외는 **사업자번호로 거른다.** 우정사업본부(우체국)는 41건(전체의 20%)이고 `merchno`가 지점마다 달라 가맹점번호·이름으로 거르면 샌다. 우편요금 반복 결제는 정상이므로 제외하지 않으면 목록이 오탐으로 덮인다
- `summary` 예: `"동일 가맹점 당일 3건 204,000원"`

### `HIGH_AMOUNT` — 고액 결제 (5건)

`apprtot >= threshold`.

- 파라미터: `threshold = 500000`
- 100만원 이상은 3건
- `summary` 예: `"단건 5,850,000원"`

### `WATCH_MCC` — 주의 업종 (5건)

`mccname`이 주의 목록에 포함.

- 파라미터: `watch_mcc = ["상품권 전문판매", "볼 링 장", "영화관", "화   원", "기타회원제형태업소4", "자사카드발행백화점"]`
- 업종명에 공백이 들어간 값이 실제로 존재한다 (`"볼 링 장"`, `"화   원"`). 목록은 DB 값 그대로 써야 한다
- **미분류가 사각지대다.** `class='A'` 190건 중 43건(23%)은 `mccname`이 NULL이라 이 규칙으로 판정할 수 없다. 업종만으로는 전수 점검이 되지 않는다는 점을 화면에 명시한다
- `summary` 예: `"주의 업종: 상품권 전문판매"`

주의 업종과 고액은 같은 거래를 동시에 잡는다 (상품권 585만원, 영화관 168만원). 의도된 동작이며 규칙별로 각각 표시한다.

## 컴포넌트

기존 구조(`services/` + `db/repositories/` + `api/v1/`)를 따른다.

**백엔드**

| 파일 | 역할 |
|---|---|
| `backend/app/anomaly/rules.py` | 규칙 카탈로그. 규칙 = `code`, `label`, `severity`, `params`, `detect()` |
| `backend/app/services/anomaly_service.py` | 규칙 실행 + 검토 상태 병합 |
| `backend/app/db/repositories/anomaly.py` | 검토 상태 upsert/조회 |
| `backend/app/api/v1/anomaly.py` | 엔드포인트 |

**공통 반환 형태.** 규칙마다 결과 모양이 다르면 화면이 규칙 수만큼 분기한다. 하나로 고정한다.

```python
@dataclass
class Finding:
    rule_code: str
    subject: str               # seq, 또는 cardno|merchno|transdate
    severity: str              # 'high' | 'medium' | 'low'
    summary: str               # 한글 사유 — 화면은 그대로 출력만 한다
    transactions: list[dict]   # 대상 거래
    amount: Decimal
    occurred_on: date
```

`summary`는 규칙이 직접 만든다. 담당자가 목록에서 근거를 바로 읽을 수 있어야 하고, 사유 조립 로직이 화면으로 새면 규칙 추가마다 프론트를 고치게 된다.

**프론트엔드**

| 파일 | 역할 |
|---|---|
| `frontend/src/views/AnomalyView.vue` | 점검 화면 |
| `frontend/src/stores/anomaly.ts` | 탐지 목록·검토 상태 |
| `frontend/src/components/layout/FunctionTabs.vue` | "점검" 탭 추가 (기존 파일 수정) |

## API

### `GET /api/v1/anomaly/findings`

쿼리 파라미터: `database_id` (필수), `rule_code`, `status` (`unreviewed` | `confirmed` | `dismissed`).

응답은 탐지 건 배열이며, 각 건에 `Finding` 필드와 함께 검토 상태가 병합되어 있다.

```json
{
  "applicable_rules": [
    { "rule_code": "OFF_HOURS", "label": "시간 외 사용", "applicable": true },
    { "rule_code": "WATCH_MCC", "label": "주의 업종", "applicable": true,
      "caveat": "업종 미분류 43건은 판정에서 제외됨" }
  ],
  "findings": [
    {
      "finding_key": "WATCH_MCC:277834",
      "rule_code": "WATCH_MCC",
      "severity": "high",
      "summary": "주의 업종: 상품권 전문판매",
      "amount": 5850000,
      "occurred_on": "2023-07-03",
      "transactions": [ { "seq": "277834", "merchname": "농협은행(주)", "apprtot": 5850000 } ],
      "review": { "status": "dismissed", "note": "교육비 집행", "reviewed_at": "2026-09-22T10:00:00Z" },
      "stale": false
    }
  ]
}
```

### `PATCH /api/v1/anomaly/findings/{finding_key}/review`

본문: `{ "database_id": "1", "status": "dismissed", "note": "교육비 집행" }`.

`(database_id, finding_key)` 기준 upsert. 저장 시 현재 지문을 함께 기록한다. 존재하지 않는 `finding_key`도 허용한다 — 탐지는 매번 계산되므로 서버가 키의 유효성을 미리 알 수 없고, 사라진 키는 다음 조회에서 자연히 목록에서 빠진다.

## 데이터 흐름

1. 화면이 `GET /anomaly/findings?database_id=1` 호출
2. `connection_pool`로 대상 DB 연결 (기존 읽기전용 연결 재사용)
3. 적용 가능한 규칙을 판정 (아래 오류 처리 참조)
4. 규칙별 SELECT 실행 → `Finding` 목록
5. `finding_key`와 지문 계산
6. `kfms`에서 해당 키들의 검토 상태 조회
7. 병합. 지문 불일치 시 `stale=true`
8. 심각도 → 일자 순 정렬해 반환

현재 200건 규모에서는 집계 쿼리 몇 개다. 캐싱은 넣지 않는다.

## 오류 처리

**대상 DB에 `v_approval`이 없는 경우.** 사용자가 다른 연결을 선택하면 규칙이 전부 깨진다. 500으로 터뜨리지 않고, 규칙 실행 전에 필요한 뷰·컬럼의 존재를 확인해 `applicable_rules`에 적용 가능 여부와 사유를 담아 반환한다. 화면은 적용 불가 규칙을 회색으로 표시한다.

**상시 오탐.** 우체국처럼 매번 걸리지만 정상인 건은 `exclude_merchbizno` 파라미터로 규칙 단계에서 제외한다. 일회성 오탐만 `dismissed`로 처리한다. 둘을 구분하지 않으면 담당자가 같은 건을 매일 dismiss하게 된다.

**규칙 하나가 실패해도 나머지는 반환한다.** 규칙은 서로 독립이므로 한 규칙의 SQL 오류가 화면 전체를 비우게 두지 않는다. 실패한 규칙은 `applicable_rules`에 오류 사유를 담는다.

## 테스트

`backend/tests/`가 비어 있고 requirements에 pytest가 없다. 규칙은 경계값에서 틀리기 가장 쉬운 종류의 코드이므로 여기에는 테스트가 필요하다. pytest를 추가한다.

**실데이터가 아니라 픽스처로 경계를 찍는다.** 실데이터 건수를 기대값으로 박으면 재적재마다 깨진다.

| 규칙 | 경계 케이스 |
|---|---|
| `OFF_HOURS` | 금요일/토요일, 22:59/23:00, 05:59/06:00 |
| `SPLIT_PAYMENT` | 동일 조합 1건/2건, 예외 사업자번호 포함/제외, 가맹점만 다른 경우 |
| `HIGH_AMOUNT` | 499,999 / 500,000 |
| `WATCH_MCC` | 목록 포함/미포함, `mccname`이 NULL |
| 공통 | `class='B'`가 어느 규칙에도 잡히지 않을 것 |
| 지문 | 묶음에 거래가 추가되면 `stale=true` |

## 범위 밖

의도적으로 넣지 않는 것.

- **통계적 이상치 탐지** — 데이터가 쌓인 뒤. 같은 `Finding` 인터페이스로 규칙을 추가하면 화면·저장 구조는 그대로 쓸 수 있다
- **시점별 스냅샷 이력** — 감사 증적이 필요해지면 그때. 현재는 검토 상태만 남긴다
- **LLM 기반 판정** — 결과가 매번 달라져 감사 근거로 쓸 수 없다
- **매입·청구 내역 탐지** — 1차는 `v_approval`만. 승인 단계에서 잡는 것이 가장 이르다
