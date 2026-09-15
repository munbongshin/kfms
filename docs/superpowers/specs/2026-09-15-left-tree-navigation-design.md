# 좌측 트리 네비게이션 UI 재구성

**날짜:** 2026-09-15
**상태:** 승인됨 (구현 대기)
**범위:** 프론트엔드 전용. 백엔드 API 변경 없음.

## 문제

현재 UI는 홈 화면의 카드를 눌러 페이지로 이동하고, 각 페이지 우상단의 "Home" 버튼으로 되돌아오는 구조다. 이 때문에:

1. **상시 네비게이션이 없다.** 질의 ↔ 이력 이동에 항상 홈을 경유해야 한다.
2. **스키마를 볼 수 없다.** Text-to-SQL 도구인데 어떤 테이블·컬럼이 있는지 확인할 방법이 UI에 없다. 사용자가 컬럼명을 모른 채 질문을 쓰게 되어 LLM이 엉뚱한 SQL을 만들 여지가 커진다.
3. **Excel 기능이 도달 불가능하다.** `ExcelUpload.vue`와 백엔드 `/excel/*` API가 모두 구현돼 있으나 어떤 뷰도 이 컴포넌트를 import하지 않는다. 사실상 죽은 기능이다.
4. **넓은 화면을 못 쓴다.** 각 뷰가 `max-width: 1400px`로 본문을 제한해 좌우가 비어 있다.

## 목표

좌측 상시 사이드바(기능 탭 + 데이터 트리) + 우측 작업 영역 구조로 재편해 위 네 가지를 해소한다.

## 결정 사항

브레인스토밍에서 확정된 선택과 그 근거:

| 결정 | 선택 | 근거 |
|---|---|---|
| 트리 성격 | **하이브리드** — 상단 기능 탭 + 하단 데이터 트리 | 스키마를 보면서 질문을 쓰는 것이 이 도구의 핵심 효용 |
| 결과 배치 | **탭 전환** (표 / 차트 / SQL) | 사이드바로 좁아진 폭을 각 뷰가 온전히 사용. SQL이 상시 확인 가능해짐 |
| 메뉴 구성 | **질의 / 데이터 / 이력** 3탭, 홈 삭제 | 상시 사이드바가 생기면 카드 메뉴 홈은 존재 이유가 없음 |
| 트리 동작 | 컬럼 클릭 → 질문창 삽입, 테이블 더블클릭 → 미리보기 | 값의 생김새를 확인하고 질문을 써야 정확도가 오름 |
| 셸 구현 | **라우터 유지** | URL·새로고침·뒤로가기 보존. 이력의 재실행 경로를 손대지 않아도 됨 |
| 미리보기 이력 | **(a) 이력에 남기되 라벨로 구분** | 백엔드 변경 0. 추적상으로도 자연스러움 |

## 레이아웃

```
┌────────────────────────────────────────────────────────┐
│ KFMS                                    [연결: retail] │  상단 바 48px
├──────────────────┬─────────────────────────────────────┤
│ [질의][데이터][이력]│                                    │
├──────────────────┤                                     │
│ 🔍 테이블 검색    │        <router-view />              │
│ ▼ Retail Sales DB│                                     │
│   ▼ retail_sales │                                     │
│       date  date │                                     │
│       gender text│                                     │
│  «               │                                     │
└──────────────────┴─────────────────────────────────────┘
   260px (접으면 48px)        남은 폭 전체
```

본문의 `max-width: 1400px` 제약은 제거한다.

## 컴포넌트

### 신규

**`components/layout/AppShell.vue`**
사이드바와 본문의 골격. 사이드바 접힘 상태(`collapsed`)를 소유하고 `localStorage`에 보존한다. 상단 바에 현재 활성 연결명을 표시한다.

**`components/layout/FunctionTabs.vue`**
질의 / 데이터 / 이력 3개 탭. 클릭 시 `router.push`. 현재 라우트명으로 활성 탭을 판정하므로 URL 직접 진입·새로고침에도 탭 상태가 맞는다.

**`components/layout/SchemaTree.vue`**
`el-tree` 기반 3단계 트리 (연결 → 테이블 → 컬럼).
- 연결 노드 펼침 시 해당 연결의 스키마를 lazy 로드
- 컬럼 노드에 타입을 회색 뱃지로 표시
- 상단 검색창으로 테이블·컬럼명 필터 (`el-tree`의 `filter-node-method`)
- 연결 노드 클릭 시 `databaseStore.setActiveConnection`
- 컬럼 클릭 → `queryStore.insertIdentifier(name)`
- 테이블 더블클릭 → `queryStore.previewTable(table, connectionId)`

**`components/results/ResultPanel.vue`**
표 / 차트 / SQL 3개 탭 래퍼. 기존 `ResultTable.vue`, `ResultChart.vue`를 그대로 품고, SQL 탭은 실행된 쿼리의 SQL을 복사 버튼과 함께 보여준다. 탭 헤더 우측에 행 수·실행시간·CSV 내려받기를 둔다.

> **주의:** 기존 `SQLPreview.vue`(다이얼로그)는 그대로 둔다. 이것은 *실행 전 승인* 용도이고, 새 SQL 탭은 *실행된 쿼리 확인* 용도로 목적이 다르다.

### 수정

**`App.vue`** — `<router-view />` 단독에서 `AppShell`로 감싸는 형태로 변경.

**`router/index.ts`** — `home` 라우트 삭제, `/` → `/query` 리다이렉트 추가.

**`views/QueryView.vue`** — 자체 `el-header`(제목 + Home 버튼) 제거. `ResultTable`/`ResultChart` 직접 배치를 `ResultPanel`로 교체. 예시 질문 카드는 결과가 없을 때만 보이는 현재 동작을 유지한다.

**`views/DatabaseView.vue`** — 자체 헤더 제거. `DatabaseManager` 아래에 `ExcelUpload`를 추가해 죽어 있던 Excel 기능에 진입점을 준다.

**`views/HistoryView.vue`** — 자체 헤더 제거.

**`components/query/QueryInput.vue`** — 내부의 `DatabaseSelector` 제거. 트리가 연결 선택기 역할을 하므로 중복이다. 활성 연결이 없을 때는 입력 대신 "좌측에서 연결을 선택하세요" 안내를 띄운다.

**`stores/database.ts`** — 스키마 캐시 추가:
- `schemas: Record<number, Record<string, ColumnInfo[]>>`
- `schemaLoading: Record<number, boolean>`
- `fetchSchema(connectionId)` — 캐시에 있으면 재요청하지 않음
- `invalidateSchema(connectionId)` — `deleteConnection` 시 함께 호출

**`stores/query.ts`** — 두 액션 추가:
- `insertIdentifier(name)` — `currentQuestion` 끝에 식별자를 공백과 함께 덧붙임
- `previewTable(tableName, connectionId)` — 아래 상세

### 삭제

**`views/HomeView.vue`** — 카드 메뉴 홈. 상시 사이드바로 대체된다.

`DatabaseSelector.vue`는 `ExcelUpload.vue`가 계속 사용하므로 **삭제하지 않는다**.

## previewTable 상세

```
queryStore.previewTable(table, connectionId)
  → api.query.execute({
      question: `[미리보기] ${table}`,
      sql: `SELECT * FROM "${table}" LIMIT 100`,
      database_id: connectionId,
      validation_approved: true,
    })
  → 성공 시 queryResults 에 적재 (일반 질의 결과와 동일 경로)
  → 질의 패널로 라우팅
```

**식별자 인용:** 테이블명은 스키마 API에서 온 신뢰 가능한 값이지만, 대문자·예약어 테이블명에서 깨지지 않도록 큰따옴표로 인용한다. 값에 `"`가 포함된 경우 `""`로 이스케이프한다. 백엔드 `get_schema`가 `public` 스키마만 반환하므로 스키마 한정(`"public"."t"`)은 하지 않는다.

**이력 기록:** `/query/execute`는 실행 결과를 항상 `query_history`에 남긴다. 미리보기도 예외가 아니므로 질문 텍스트를 `[미리보기] <테이블명>`으로 남겨 이력에서 구분 가능하게 한다. 백엔드는 변경하지 않는다.

## 데이터 흐름

```
databaseStore.activeConnections  →  트리 1단계
        ↓ 연결 노드 펼침
databaseStore.fetchSchema(id)    →  트리 2·3단계 (캐시)
        ↓ 컬럼 클릭
queryStore.insertIdentifier()    →  질문 입력창
        ↓ 테이블 더블클릭
queryStore.previewTable()        →  queryResults  →  ResultPanel
```

`databaseStore`가 연결·스키마의 단일 출처이고, 트리는 이를 읽기만 한다.

## 에러 및 빈 상태

| 상황 | 표시 |
|---|---|
| 연결 0개 | 트리 자리에 "등록된 연결이 없습니다 · [연결 추가]" (데이터 패널로 이동) |
| 스키마 로드 실패 | 해당 연결 노드 아래 "스키마를 불러올 수 없습니다 · [다시 시도]" |
| 스키마 로드 중 | 노드에 로딩 스피너 |
| 테이블 0개 | "테이블이 없습니다" |
| 활성 연결 없음 | 질문 입력창 대신 "좌측에서 연결을 선택하세요" |
| 미리보기 실패 | 기존 `ElMessage.error` 경로를 그대로 사용 |

## 검증

자동화 테스트가 없는 코드베이스이므로 수동 검증한다.

1. 세 패널 전환 시 사이드바 유지, URL 변경, 새로고침 후 같은 패널 복원
2. `/` 접속 시 질의 패널로 리다이렉트
3. 트리 연결 노드 펼침 → 테이블·컬럼 표시, 두 번째 펼침에서 네트워크 재요청 없음
4. 컬럼 클릭 → 질문창에 이름 삽입
5. 테이블 더블클릭 → 100행 표시, 이력에 `[미리보기] …`로 기록
6. 결과 탭 3개(표·차트·SQL) 전환 및 CSV 내려받기
7. 이력의 "재실행" → 질의 패널로 이동하며 질문 적재 (기존 동작 보존)
8. 데이터 패널에서 Excel 업로드 진입 가능
9. 사이드바 접기/펴기 후 새로고침해도 상태 유지
10. 연결 0개 / 스키마 실패 시 빈 상태 표시
11. 1280px·1920px 폭 레이아웃 확인

## 범위 밖

- 백엔드 API 변경 (`skip_history` 플래그 등)
- 홈 대시보드 (통계 화면)
- 다크 모드
- 트리에서의 연결 생성·삭제 (데이터 패널에 그대로 둠)
