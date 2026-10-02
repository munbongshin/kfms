# KFMS 개발 재현 가이드

## 프로젝트 개요

**KFMS (Knowledge Flow Management System)**는 법인카드 데이터를 자연어 질문으로 조회하고 이상 거래를 자동 점검하는 시스템입니다.

### 핵심 기능
- 🗣️ **Text-to-SQL**: 한국어 질문을 SQL로 변환하여 데이터 조회
- 🔍 **이상 거래 점검**: 규칙 기반 자동 검사 (고액/분할결제/주의업종/시간외)
- 👥 **역할 기반 권한**: 관리자/감사담당/조회 역할별 접근 제어
- 🌐 **다국어 지원**: 한글/영어 언어 토글
- 📊 **엑셀 연동**: 파일 업로드/다운로드, 컬럼 한글명 관리
- 📝 **이력 관리**: 모든 질의/변경 사항 추적 및 감사 로그

---

## 1. 기술 스택

### Frontend
```json
{
  "framework": "Vue 3 (Composition API)",
  "ui": "Element Plus 2.5+",
  "state": "Pinia",
  "router": "Vue Router 4",
  "charts": "Apache ECharts 5",
  "editor": "CodeMirror 6 (SQL)",
  "http": "Axios",
  "build": "Vite 5",
  "language": "TypeScript"
}
```

### Backend
```python
{
  "framework": "FastAPI 0.109",
  "async_db": "SQLAlchemy 2.0 (asyncpg)",
  "validation": "Pydantic 2.5",
  "auth": "HMAC + scrypt",
  "excel": "pandas + openpyxl",
  "scheduler": "APScheduler",
  "llm": "httpx (Ollama/Groq/OpenAI 호환)",
  "crypto": "cryptography (Fernet)",
  "holidays": "holidays 0.105"
}
```

### Database
- **PostgreSQL 16**: 메타 정보(kfms) + 데이터(retail)
- **Docker**: `docker-compose.yml`로 간편 실행

---

## 2. 프로젝트 구조

```
kfms/
├── backend/
│   ├── app/
│   │   ├── api/v1/          # REST API 엔드포인트
│   │   │   ├── auth.py      # 로그인/사용자 관리
│   │   │   ├── databases.py # DB 연결 관리
│   │   │   ├── query.py     # Text-to-SQL 질의
│   │   │   ├── history.py   # 질의 이력
│   │   │   ├── anomaly.py   # 이상 거래 점검
│   │   │   ├── column_labels.py  # 컬럼 한글명
│   │   │   ├── excel.py     # 엑셀 업로드
│   │   │   └── reports.py   # 보고서 저장
│   │   ├── services/        # 비즈니스 로직
│   │   │   ├── llm_service.py       # LLM 통신
│   │   │   ├── query_service.py     # SQL 생성/실행
│   │   │   ├── anomaly_service.py   # 점검 규칙 엔진
│   │   │   ├── excel_service.py     # 엑셀 처리
│   │   │   └── holiday_sync.py      # 공휴일 동기화
│   │   ├── db/
│   │   │   ├── models.py    # SQLAlchemy 모델
│   │   │   ├── repositories/  # 데이터 접근 계층
│   │   │   ├── connection_pool.py  # 동적 연결 풀
│   │   │   └── column_labels.py    # 한글명 매핑
│   │   ├── auth/            # 인증/권한
│   │   ├── anomaly/         # 점검 규칙 정의
│   │   ├── llm/             # LLM 플랫폼 추상화
│   │   ├── i18n.py          # 서버 메시지 번역
│   │   ├── i18n_catalog.py  # 한/영 메시지 카탈로그
│   │   ├── config.py        # 환경 설정
│   │   └── main.py          # FastAPI 앱 진입점
│   ├── tests/               # pytest 테스트
│   └── requirements.txt
│
├── frontend/
│   ├── src/
│   │   ├── views/           # 페이지 컴포넌트
│   │   │   ├── QueryView.vue    # 질의 화면
│   │   │   ├── HistoryView.vue  # 이력 화면
│   │   │   ├── AnomalyView.vue  # 점검 화면
│   │   │   ├── AdminView.vue    # 관리 화면
│   │   │   └── SettingsView.vue # 설정 화면
│   │   ├── components/      # 재사용 컴포넌트
│   │   │   ├── layout/      # 레이아웃 (상단바, 트리, 탭)
│   │   │   ├── query/       # 질의 입력/SQL 미리보기
│   │   │   ├── results/     # 결과 테이블/차트
│   │   │   ├── database/    # DB 연결 관리
│   │   │   └── anomaly/     # 점검 기준 설정
│   │   ├── stores/          # Pinia 상태 관리
│   │   ├── services/api.ts  # Axios API 클라이언트
│   │   ├── i18n/            # 다국어 번역
│   │   ├── router/          # 라우팅
│   │   └── main.ts
│   └── package.json
│
├── docker/
│   └── init/                # 샘플 데이터 DB 초기화 (01_schema.sql, 02_load.sql)
├── docker-compose.yml
└── README.md
```

---

## 3. 데이터베이스 설계

메타 정보 DB(`kfms`)의 실제 테이블입니다. 아래 목록은 운영 중인 DB의 `information_schema`에서 뽑은 것이므로 그대로 만들면 됩니다.
(테이블은 `backend/app/db/models.py`의 SQLAlchemy 모델이 만들고, 이 환경에서는 alembic 대신 DDL을 직접 적용했습니다.)

| 테이블 | 용도 |
|---|---|
| app_users | 로그인 계정(역할 admin/auditor/viewer) |
| database_connections | 조회 대상 DB 연결(비밀번호는 Fernet 암호화), 분석 제외 테이블 |
| query_history | 질문·SQL·결과·북마크 |
| column_labels | 컬럼 한글명(연결 단위, 테이블별 예외) |
| expression_terms | 계산 컬럼 용어(합계·건수 …) |
| anomaly_settings / anomaly_setting_history | 점검 기준과 변경 이력 |
| anomaly_review | 점검 결과 확인 처리 |
| synced_holidays / holiday_sync | 동기화된 임시공휴일과 동기화 상태·서비스키 |
| saved_reports | 예약 실행하는 저장 보고서 |
| glossary_terms | 업무 용어 사전 |
| eval_cases / eval_runs | 정확도 평가 문제와 실행 결과 |
| llm_settings | 사용할 LLM 플랫폼과 플랫폼별 프로필 |
| excel_uploads | 올린 엑셀과 만료 시각 |
| audit_log | 변경·카드번호 열람 감사 로그 |

```text
anomaly_review
  id int4 NOT NULL
  database_id varchar(255) NOT NULL
  finding_key varchar(200) NOT NULL
  rule_code varchar(40) NOT NULL
  status varchar(20) NOT NULL
  fingerprint varchar(64) NOT NULL
  note text
  reviewed_at timestamptz NOT NULL

anomaly_setting_history
  id int4 NOT NULL
  changed_at timestamptz NOT NULL
  changed_by varchar(60) NOT NULL
  before json NOT NULL
  after json NOT NULL
  changes json NOT NULL

anomaly_settings
  id int4 NOT NULL
  params json NOT NULL
  updated_at timestamptz NOT NULL

app_users
  id int4 NOT NULL
  username varchar(60) NOT NULL
  display_name varchar(100) NOT NULL
  password_hash varchar(300) NOT NULL
  role varchar(20) NOT NULL
  is_active bool NOT NULL
  created_at timestamptz NOT NULL
  last_login_at timestamptz

audit_log
  id int4 NOT NULL
  at timestamptz NOT NULL
  username varchar(60) NOT NULL
  role varchar(20) NOT NULL
  action varchar(60) NOT NULL
  target varchar(500) NOT NULL
  detail json NOT NULL
  ip varchar(64) NOT NULL

column_labels
  id int4 NOT NULL
  connection_id int4 NOT NULL
  table_key varchar(255)
  column_name varchar(128) NOT NULL
  label varchar(100) NOT NULL
  updated_at timestamptz NOT NULL

database_connections
  id int4 NOT NULL
  name varchar(255) NOT NULL
  host varchar(255) NOT NULL
  port int4
  database varchar(255) NOT NULL
  username varchar(255) NOT NULL
  password varchar(255) NOT NULL
  is_active bool
  is_read_only bool
  created_at timestamptz
  updated_at timestamptz
  excluded_tables json NOT NULL

eval_cases
  id int4 NOT NULL
  question text NOT NULL
  expected_sql text NOT NULL
  database_id varchar(255) NOT NULL
  created_by varchar(60) NOT NULL
  created_at timestamptz NOT NULL

eval_runs
  id int4 NOT NULL
  database_id varchar(255) NOT NULL
  status varchar(20) NOT NULL
  provider varchar(60) NOT NULL
  model varchar(200) NOT NULL
  total int4 NOT NULL
  passed int4 NOT NULL
  seconds float8
  error text
  details json
  started_by varchar(60) NOT NULL
  started_at timestamptz NOT NULL

excel_uploads
  id int4 NOT NULL
  filename varchar(255) NOT NULL
  table_name varchar(255) NOT NULL
  row_count int4
  column_count int4
  schema_info jsonb
  created_at timestamptz
  expires_at timestamptz

expression_terms
  func varchar(20) NOT NULL
  label varchar(50) NOT NULL
  updated_at timestamptz NOT NULL

glossary_terms
  id int4 NOT NULL
  term varchar(100) NOT NULL
  definition text NOT NULL
  created_at timestamptz NOT NULL

holiday_sync
  id int4 NOT NULL
  service_key text
  last_synced_at timestamptz
  last_status varchar(20)
  last_error text
  last_source varchar(20)

llm_settings
  id int4 NOT NULL
  provider varchar(40)
  profiles json NOT NULL
  updated_at timestamptz NOT NULL

query_history
  id int4 NOT NULL
  question text NOT NULL
  generated_sql text NOT NULL
  database_id varchar(255) NOT NULL
  status varchar(20) NOT NULL
  results jsonb
  error_message text
  execution_time_ms int4
  row_count int4
  llm_provider varchar(50)
  llm_model varchar(100)
  validation_approved bool
  created_at timestamptz
  is_bookmarked bool NOT NULL

saved_reports
  id int4 NOT NULL
  name varchar(200) NOT NULL
  question text NOT NULL
  sql text NOT NULL
  database_id varchar(255) NOT NULL
  frequency varchar(20) NOT NULL
  run_hour int4 NOT NULL
  run_weekday int4
  run_day int4
  is_active bool NOT NULL
  next_run_at timestamptz NOT NULL
  last_run_at timestamptz
  last_status varchar(20)
  last_error text
  last_row_count int4
  last_results json
  created_by varchar(60) NOT NULL
  created_at timestamptz NOT NULL

synced_holidays
  day varchar(10) NOT NULL
  name varchar(100) NOT NULL
  source varchar(20) NOT NULL
  fetched_at timestamptz NOT NULL

```

---

## 4. 핵심 기능 구현 순서

### Phase 1: 프로젝트 기반 설정
1. Docker PostgreSQL 설정
2. Backend FastAPI 기본 구조
3. Frontend Vue 3 + Element Plus 설정
4. 환경 변수 (.env) 설정

### Phase 2: 인증/권한 시스템
1. User 모델 + scrypt 비밀번호 해싱
2. HMAC 토큰 기반 인증 (auth.py)
3. 역할 기반 데코레이터 (@ADMIN, @AUDITOR)
4. 로그인 화면 + AuthStore

### Phase 3: DB 연결 관리
1. database_connections 테이블
2. Fernet 암호화 (비밀번호/API 키)
3. 동적 연결 풀 (DatabaseConnectionPool)
4. 연결 추가/수정/삭제 API
5. DatabaseManager 컴포넌트

### Phase 4: Text-to-SQL 엔진
1. LLM 플랫폼 추상화 (Ollama/Groq/etc.)
2. 스키마 조회 + 프롬프트 구성
3. SQL 생성 + 안전성 검증 (SELECT만 허용)
4. SQL 실행 + 결과 반환
5. QueryView + ResultTable/Chart

### Phase 5: 컬럼 한글명 시스템
1. column_label_overrides 테이블
2. 테이블/연결 단위 매핑
3. 엑셀 일괄 입력/내보내기
4. expression_terms (계산 컬럼 용어)
5. 비관리자에게는 한글명만 노출

### Phase 6: 질의 이력
1. query_history 테이블
2. 결과 저장 (JSONB)
3. 재실행/북마크 기능
4. HistoryView 컴포넌트

### Phase 7: 이상 거래 점검
1. 점검 규칙 정의 (anomaly/rules.py)
   - HIGH_AMOUNT: 고액 결제
   - SPLIT_PAYMENT: 분할 결제
   - WATCH_CATEGORIES: 주의 업종
   - OFF_HOURS: 주말/공휴일/심야
2. anomaly_settings + history 테이블
3. 규칙 켜기/끄기, 심각도, 세부 기준
4. 한국 공휴일 자동 동기화
5. AnomalyView + 상세 화면

### Phase 8: 엑셀 업로드
1. 파일 업로드 + pandas 파싱
2. 파일 이름으로 스키마 이름을 정하고(`kfms_upload.<이름>`), 한글·숫자·밑줄이 남도록 컬럼·테이블 이름 정리
3. 업로드 테이블 생성 (기본 24시간 후 만료, 만료 후 유예 기간이 지나면 스케줄러가 삭제)
4. 값 모양으로 컬럼 타입 추정 (pandas 방식)
5. ExcelUpload 컴포넌트

### Phase 9: 다국어 (i18n)
1. Frontend: t('한글') → 영어 카탈로그
2. Backend: Accept-Language 헤더
3. 서버 메시지 JSON 번역 (데이터 제외)
4. LanguageSwitch 컴포넌트
5. localStorage에 언어 선택 저장

### Phase 10: 관리 기능
1. 사용자 관리 (추가/수정/삭제)
2. 정확도 평가 (eval.py)
3. 감사 로그 조회
4. 도움말 화면

---

## 5. 주요 API 엔드포인트

`app.openapi()`에서 뽑은 실제 목록입니다(총 81개). 모든 경로 앞에 `/api/v1`이 붙고, `/health`와 `/auth/status|setup|login`을 뺀 나머지는 로그인이 필요합니다.

```text
GET     /anomaly/categories
GET     /anomaly/findings
PATCH   /anomaly/findings/review
GET     /anomaly/findings/transactions
POST    /anomaly/holidays
POST    /anomaly/holidays/check
PUT     /anomaly/holidays/service-key
GET     /anomaly/holidays/status
POST    /anomaly/holidays/sync
GET     /anomaly/settings
PUT     /anomaly/settings
GET     /anomaly/settings/history
POST    /anomaly/settings/history/{entry_id}/restore
GET     /anomaly/sources
GET     /audit-log
POST    /auth/login
GET     /auth/me
PATCH   /auth/me
POST    /auth/setup
GET     /auth/status
GET     /databases
POST    /databases
DELETE  /databases/{connection_id}
PATCH   /databases/{connection_id}
GET     /databases/{connection_id}/column-labels
PUT     /databases/{connection_id}/column-labels
GET     /databases/{connection_id}/column-labels/export
POST    /databases/{connection_id}/column-labels/import
DELETE  /databases/{connection_id}/column-labels/{label_id}
PUT     /databases/{connection_id}/excluded-tables
GET     /databases/{connection_id}/schema
GET     /databases/{connection_id}/tables/{table}/rows
POST    /databases/{connection_id}/test
GET     /eval/cases
POST    /eval/cases
POST    /eval/cases/from-bookmarks
DELETE  /eval/cases/{case_id}
POST    /eval/run
GET     /eval/runs
GET     /eval/runs/{run_id}
POST    /excel/cleanup
GET     /excel/table-name
POST    /excel/upload
GET     /excel/uploads
DELETE  /excel/{upload_id}
POST    /excel/{upload_id}/extend
GET     /excel/{upload_id}/preview
GET     /expression-terms
DELETE  /expression-terms/{func}
PUT     /expression-terms/{func}
GET     /glossary
POST    /glossary
DELETE  /glossary/{term_id}
PUT     /glossary/{term_id}
GET     /health
DELETE  /history
GET     /history
GET     /history/stats/summary
DELETE  /history/{history_id}
GET     /history/{history_id}
PATCH   /history/{history_id}/bookmark
GET     /llm-settings
PUT     /llm-settings
POST    /llm-settings/models
POST    /llm-settings/test
POST    /query/execute
POST    /query/generate
POST    /query/generate-and-execute
POST    /query/rerun/{history_id}
POST    /query/validate
GET     /reports
POST    /reports
DELETE  /reports/{report_id}
GET     /reports/{report_id}
PATCH   /reports/{report_id}
POST    /reports/{report_id}/run
GET     /users
POST    /users
GET     /users/check
DELETE  /users/{user_id}
PATCH   /users/{user_id}
```

역할: `admin` 은 전부, `auditor` 는 점검(anomaly) 화면과 기준 설정, `viewer` 는 질의·이력 조회. 데이터·관리·설정 화면과 SQL 열람은 관리자 전용입니다.

---

## 6. 환경 설정

### backend/.env
```bash
# Application
APP_NAME=KFMS
DEBUG=False

# Database (metadata)
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5434/kfms

# LLM Provider
LLM_PROVIDER=ollama
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3.1

# Security (자동 생성됨)
FERNET_KEY=

# Server
HOST=0.0.0.0
PORT=8000
CORS_ORIGINS=http://localhost:5173

# Excel
EXCEL_UPLOAD_MAX_SIZE_MB=50
EXCEL_TABLE_TTL_HOURS=24

# Query
QUERY_RESULT_LIMIT=1000
QUERY_TIMEOUT=30

# Holiday sync
HOLIDAY_SYNC_ENABLED=True
```

### frontend/.env
```bash
VITE_API_BASE_URL=http://localhost:8000
```

---

## 7. 실행 방법

### 7.1 PostgreSQL 시작
```bash
docker-compose up -d
```

### 7.2 Backend 실행
```bash
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 7.3 Frontend 실행
```bash
cd frontend
npm install
npm run dev
```

### 7.4 초기 관리자 생성

웹 화면을 처음 열면 관리자 계정을 만드는 화면이 나옵니다(`GET /auth/status` 가 `setup_required: true` 일 때, `POST /auth/setup`). 별도 스크립트는 필요 없습니다.

---

## 8. 핵심 구현 패턴

> 아래 코드는 구조를 설명하기 위해 **줄여 쓴 예시**입니다. 실제 구현은 각 절의 파일(`app/utils/sql_validator.py`, `app/db/connection_pool.py`, `app/services/prompt_context.py` 등)을 보세요.

### 8.1 SQL 안전성 검증
```python
# backend/app/utils/sql_validator.py
def validate_sql(sql: str) -> tuple[bool, list[str]]:
    """SELECT만 허용, DDL/DML 차단"""
    warnings = []
    
    # sqlparse로 파싱
    parsed = sqlparse.parse(sql.strip())
    if not parsed:
        warnings.append("SQL이 비어 있습니다")
        return False, warnings
    
    for stmt in parsed:
        stmt_type = stmt.get_type()
        if stmt_type != 'SELECT':
            warnings.append(f"SELECT만 허용됩니다 ({stmt_type} 감지)")
            return False, warnings
    
    # 위험 키워드 검사
    dangerous = ['DROP', 'DELETE', 'UPDATE', 'INSERT', 'TRUNCATE', 'ALTER']
    upper_sql = sql.upper()
    for keyword in dangerous:
        if keyword in upper_sql:
            warnings.append(f"허용되지 않는 키워드: {keyword}")
            return False, warnings
    
    return True, warnings
```

### 8.2 동적 DB 연결 풀
```python
# backend/app/db/connection_pool.py
class DatabaseConnectionPool:
    def __init__(self):
        self._engines: dict[int, AsyncEngine] = {}
        self._locks: dict[int, asyncio.Lock] = {}
    
    async def get_engine(self, connection_id: int) -> AsyncEngine:
        """연결 ID로 엔진 반환 (캐시)"""
        if connection_id not in self._engines:
            async with self._get_lock(connection_id):
                if connection_id not in self._engines:
                    conn = await self._fetch_connection(connection_id)
                    self._engines[connection_id] = create_async_engine(
                        f"postgresql+asyncpg://{conn.username}:{decrypt(conn.password_encrypted)}"
                        f"@{conn.host}:{conn.port}/{conn.database}"
                    )
        return self._engines[connection_id]
    
    async def execute_query(self, connection_id: int, sql: str, params: dict = None):
        """SQL 실행"""
        engine = await self.get_engine(connection_id)
        async with engine.begin() as conn:
            result = await conn.execute(text(sql), params or {})
            return [dict(row) for row in result]
```

### 8.3 LLM 프롬프트 구성
```python
# backend/app/services/prompt_context.py
def build_text2sql_prompt(question: str, schema: dict) -> str:
    """Text-to-SQL 프롬프트"""
    tables_desc = []
    for table in schema['tables']:
        cols = ', '.join([
            f"{col['name']}({col['label'] or col['comment'] or col['type']})"
            for col in table['columns']
        ])
        tables_desc.append(f"- {table['name']}: {cols}")
    
    return f"""당신은 PostgreSQL 전문가입니다. 다음 스키마를 보고 자연어 질문을 SQL로 변환하세요.

## 스키마
{chr(10).join(tables_desc)}

## 규칙
1. SELECT 문만 생성하세요
2. 컬럼명은 정확히 일치해야 합니다
3. WHERE 절에 적절한 조건을 추가하세요
4. LIMIT는 최대 1000으로 제한하세요

## 질문
{question}

## SQL (코드 블록 없이 순수 SQL만 출력):
"""
```

### 8.4 한글명 적용
```python
# backend/app/db/column_labels.py
def apply_labels(schema: dict, overrides: list[Override]) -> dict:
    """스키마에 한글명 적용"""
    override_map = {
        (o.table_key, o.column_name): o.label
        for o in overrides
    }
    
    for table in schema['tables']:
        for col in table['columns']:
            # 테이블별 우선, 없으면 전체 연결 대상
            label = (
                override_map.get((table['name'], col['name']))
                or override_map.get((None, col['name']))
                or col.get('comment')
                or col['name']
            )
            col['label'] = label
    
    return schema
```

### 8.5 비관리자용 한글명 변환
```python
# backend/app/services/result_labels.py
def relabel_rows(rows: list[dict], schema: dict) -> list[dict]:
    """비관리자에게는 영문 컬럼명 → 한글명 변환"""
    if not rows:
        return rows
    
    # 컬럼명 → 한글명 매핑
    label_map = {}
    for table in schema['tables']:
        for col in table['columns']:
            label_map[col['name']] = col['label']
    
    # 한글명 중복 시 (2), (3) 추가
    seen = {}
    for name, label in label_map.items():
        if label in seen:
            seen[label] += 1
            label_map[name] = f"{label} ({seen[label]})"
        else:
            seen[label] = 1
    
    # 행 변환
    return [
        {label_map.get(k, f"이름 미지정 {i}"): v for i, (k, v) in enumerate(row.items(), 1)}
        for row in rows
    ]
```

### 8.6 점검 규칙 엔진
```python
# backend/app/anomaly/rules.py
class HighAmountRule(AnomalyRule):
    """고액 결제 점검"""
    def check(self, rows: list[dict], spec: dict) -> list[Finding]:
        findings = []
        threshold_map = spec.get('threshold_map', {})  # 업종별 기준
        default = spec.get('threshold', 1000000)
        
        for row in rows:
            amount = row.get('apprtot', 0)
            category = row.get('merchcate', '')
            limit = threshold_map.get(category, default)
            
            if amount >= limit:
                findings.append(Finding(
                    rule='HIGH_AMOUNT',
                    severity=spec.get('severity', 'high'),
                    summary=f"단건 {int(amount):,}원",
                    keys=[row['seq']],
                    detail={}
                ))
        return findings
```

---

## 9. 보안 고려사항

1. **SQL Injection 방지**: Parameterized query 사용
2. **XSS 방지**: Element Plus 자동 이스케이프
3. **CSRF**: 쿠키를 쓰지 않고 Authorization 헤더의 토큰으로만 인증
4. **비밀번호**: scrypt + salt (app.auth.security)
5. **DB 비밀번호/API 키**: Fernet 대칭 암호화
6. **역할 기반 접근**: 데코레이터로 엔드포인트 보호
7. **카드번호 마스킹**: 조회 역할에게는 `****-****-1234` 형태
8. **감사 로그**: 모든 변경/조회 기록

---

## 10. 테스트

### Backend
```bash
cd backend
pytest -v
# 558 passed 예상
```

### Frontend
```bash
cd frontend
npm test
# 54 passed 예상

npx vue-tsc --noEmit
# No errors
```

---

## 11. 배포

이 저장소에는 운영용 Dockerfile이 없습니다. 지금 있는 것은 개발용 PostgreSQL 컨테이너(`docker-compose.yml`, 포트 5434)뿐이며,
백엔드와 프런트엔드는 다음처럼 직접 실행합니다.

```bash
# 백엔드
cd backend && uvicorn app.main:app --host 0.0.0.0 --port 8000
# 프런트엔드 (정적 파일로 빌드해서 웹 서버에 올리고 /api 를 백엔드로 넘김)
cd frontend && npm run build
```

운영에 올릴 때 정해야 할 것: `FERNET_KEY`(변경하면 저장된 연결 비밀번호를 읽지 못함), `CORS_ORIGINS`, DB 계정,
스케줄러를 돌릴 서버 한 대(같은 DB에 여러 서버가 스케줄러를 켜면 같은 보고서가 중복 실행됨).

---

## 12. 추가 개선 아이디어

1. **WebSocket**: 실시간 질의 진행 상황
2. **Redis**: 스키마 캐싱, 세션 관리
3. **Celery**: 장시간 질의 비동기 처리
4. **Elasticsearch**: 전체 텍스트 검색
5. **Grafana**: 모니터링 대시보드
6. **더 많은 LLM**: Claude, GPT-4 지원
7. **고급 점검**: ML 기반 이상 탐지
8. **모바일 앱**: React Native 버전

---

## 13. 문제 해결

### LLM 연결 실패
```bash
# Ollama가 실행 중인지 확인
curl http://localhost:11434/api/tags

# 모델 다운로드
ollama pull llama3.1
```

### DB 연결 오류
```bash
# PostgreSQL 상태 확인
docker ps | grep postgres

# 로그 확인
docker logs kfms-postgres
```

### 프론트엔드 빌드 오류
```bash
# 캐시 삭제 후 재설치
rm -rf node_modules package-lock.json
npm install
```

---

## 14. 참고

- 라이선스는 이 저장소에 지정되어 있지 않습니다(README의 MIT 문구는 확인이 필요합니다).
- 외부 서비스: Ollama(로컬), Groq(상용 API), OpenAI 호환 서버. 화면 라이브러리는 Element Plus, DB는 PostgreSQL.

---

**이 가이드는 구조와 순서를 설명하는 문서입니다.** 3절(DB 구조)과 5절(API 목록)은 실제 DB와 라우트에서 뽑은 내용이고,
8절의 코드는 이해를 돕기 위해 줄여 쓴 예시입니다. 세부 동작은 각 절에 적은 파일의 실제 코드를 기준으로 하세요.
