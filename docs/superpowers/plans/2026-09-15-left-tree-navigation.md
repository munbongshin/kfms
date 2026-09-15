# 좌측 트리 네비게이션 UI 재구성 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 카드 메뉴 홈과 페이지별 헤더를 걷어내고, 좌측 상시 사이드바(기능 탭 + 스키마 트리) + 우측 탭형 결과 영역 구조로 프론트엔드를 재편한다.

**Architecture:** `App.vue`가 `AppShell`로 감싸지고 기존 3개 라우트는 본문 패널로만 들어간다. 라우터는 유지하므로 URL·새로고침·뒤로가기가 계속 동작한다. 사이드바의 스키마 트리는 `databaseStore`를 단일 출처로 읽고, 스키마는 연결별로 한 번만 로드해 캐시한다.

**Tech Stack:** Vue 3 (Composition API, `<script setup>`), TypeScript, Pinia, Vue Router 4, Element Plus, ECharts

**Spec:** `docs/superpowers/specs/2026-09-15-left-tree-navigation-design.md`

## Global Constraints

- **백엔드 변경 금지.** 이번 작업은 `frontend/` 안에서만 이뤄진다. `backend/` 파일을 수정해야 할 것 같으면 멈추고 보고할 것.
- **테스트 프레임워크 없음.** 이 저장소에는 프론트엔드 테스트 러너가 없다(`package.json`에 test 스크립트 없음). 따라서 각 태스크의 자동 게이트는 **타입 체크**(`npx vue-tsc --noEmit`)이고, 나머지는 명시된 **브라우저 수동 확인**이다. 태스크 수행 중 임의로 Vitest 등을 추가하지 말 것 — 스펙 범위 밖이다.
- **검증 전제:** 브라우저 확인 전에 세 서비스가 떠 있어야 한다. `docker compose up -d` → `cd backend && uvicorn app.main:app --port 8000` → `cd frontend && npm run dev`. **Docker를 백엔드보다 먼저** 띄울 것(순서가 뒤바뀌면 등록된 연결이 풀에 복원되지 않아 모든 쿼리가 실패한다).
- **기존 동작 보존:** 이력의 "재실행"(`HistoryList.vue`의 `router.push('/query')`)은 계속 동작해야 한다.
- 모든 신규 컴포넌트는 `<script setup lang="ts">`를 쓰고 기존 파일들의 스타일 관례(scoped CSS, Element Plus 컴포넌트)를 따른다.

---

### Task 1: 셸 골격과 라우팅

사이드바 프레임과 기능 탭을 세우고, 뷰에서 중복 헤더를 걷어낸다. 스키마 트리는 Task 3에서 채우므로 이 태스크에서는 자리만 비워 둔다.

**Files:**
- Create: `frontend/src/components/layout/AppShell.vue`
- Create: `frontend/src/components/layout/FunctionTabs.vue`
- Modify: `frontend/src/App.vue`
- Modify: `frontend/src/router/index.ts`
- Modify: `frontend/src/views/QueryView.vue` (헤더 제거)
- Modify: `frontend/src/views/DatabaseView.vue` (헤더 제거)
- Modify: `frontend/src/views/HistoryView.vue` (헤더 제거)
- Delete: `frontend/src/views/HomeView.vue`

**Interfaces:**
- Consumes: 없음 (첫 태스크)
- Produces: `AppShell`이 기본 슬롯에 본문을 렌더한다. 사이드바 하단에 `<!-- SchemaTree mount point -->` 주석을 남겨 Task 3이 그 자리에 삽입한다.

- [ ] **Step 1: `FunctionTabs.vue` 작성**

```vue
<template>
  <nav class="function-tabs">
    <button
      v-for="tab in tabs"
      :key="tab.name"
      class="tab"
      :class="{ active: route.name === tab.name }"
      :title="tab.label"
      @click="router.push({ name: tab.name })"
    >
      <el-icon><component :is="tab.icon" /></el-icon>
      <span v-if="!collapsed" class="label">{{ tab.label }}</span>
    </button>
  </nav>
</template>

<script setup lang="ts">
import { useRoute, useRouter } from 'vue-router'
import { ChatLineSquare, Coin, Clock } from '@element-plus/icons-vue'

defineProps<{ collapsed: boolean }>()

const route = useRoute()
const router = useRouter()

const tabs = [
  { name: 'query', label: '질의', icon: ChatLineSquare },
  { name: 'databases', label: '데이터', icon: Coin },
  { name: 'history', label: '이력', icon: Clock },
]
</script>

<style scoped>
.function-tabs {
  display: flex;
  border-bottom: 1px solid #e4e7ed;
}

.tab {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  padding: 12px 4px;
  border: none;
  border-bottom: 2px solid transparent;
  background: transparent;
  color: #606266;
  font-size: 13px;
  cursor: pointer;
}

.tab:hover {
  color: #409eff;
  background: #f5f7fa;
}

.tab.active {
  color: #409eff;
  border-bottom-color: #409eff;
  font-weight: 600;
}
</style>
```

- [ ] **Step 2: `AppShell.vue` 작성**

```vue
<template>
  <div class="app-shell">
    <header class="top-bar">
      <span class="brand">KFMS</span>
      <span v-if="databaseStore.activeConnection" class="active-conn">
        <el-tag size="small" type="success">
          {{ databaseStore.activeConnection.name }}
        </el-tag>
      </span>
    </header>

    <div class="body">
      <aside class="sidebar" :class="{ collapsed }">
        <FunctionTabs :collapsed="collapsed" />

        <div v-show="!collapsed" class="tree-area">
          <!-- SchemaTree mount point (Task 3) -->
        </div>

        <button class="collapse-toggle" :title="collapsed ? '펼치기' : '접기'" @click="toggle">
          {{ collapsed ? '»' : '«' }}
        </button>
      </aside>

      <main class="content">
        <slot />
      </main>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, watch } from 'vue'
import FunctionTabs from './FunctionTabs.vue'
import { useDatabaseStore } from '../../stores/database'

const STORAGE_KEY = 'kfms.sidebar.collapsed'

const databaseStore = useDatabaseStore()
const collapsed = ref(false)

onMounted(() => {
  collapsed.value = localStorage.getItem(STORAGE_KEY) === 'true'
  if (databaseStore.connections.length === 0) {
    databaseStore.fetchConnections(true)
  }
})

watch(collapsed, (v) => localStorage.setItem(STORAGE_KEY, String(v)))

function toggle() {
  collapsed.value = !collapsed.value
}
</script>

<style scoped>
.app-shell {
  display: flex;
  flex-direction: column;
  height: 100vh;
}

.top-bar {
  display: flex;
  align-items: center;
  gap: 12px;
  height: 48px;
  padding: 0 16px;
  background: #fff;
  border-bottom: 1px solid #e4e7ed;
  flex-shrink: 0;
}

.brand {
  font-weight: 700;
  color: #303133;
}

.active-conn {
  margin-left: auto;
}

.body {
  display: flex;
  flex: 1;
  min-height: 0;
}

.sidebar {
  position: relative;
  display: flex;
  flex-direction: column;
  width: 260px;
  background: #fff;
  border-right: 1px solid #e4e7ed;
  flex-shrink: 0;
  transition: width 0.15s ease;
}

.sidebar.collapsed {
  width: 48px;
}

.tree-area {
  flex: 1;
  overflow: auto;
  padding: 8px;
  min-height: 0;
}

.collapse-toggle {
  height: 28px;
  border: none;
  border-top: 1px solid #e4e7ed;
  background: #fafafa;
  color: #909399;
  cursor: pointer;
  flex-shrink: 0;
}

.content {
  flex: 1;
  overflow: auto;
  padding: 16px;
  background: #f5f7fa;
  min-width: 0;
}
</style>
```

- [ ] **Step 3: `App.vue` 교체**

```vue
<template>
  <AppShell>
    <router-view />
  </AppShell>
</template>

<script setup lang="ts">
import AppShell from './components/layout/AppShell.vue'
</script>

<style>
#app {
  font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
}
</style>
```

- [ ] **Step 4: `router/index.ts` 교체**

`HomeView` import와 `home` 라우트를 지우고 `/`를 `/query`로 리다이렉트한다.

```ts
import { createRouter, createWebHistory, RouteRecordRaw } from 'vue-router'

const routes: Array<RouteRecordRaw> = [
  {
    path: '/',
    redirect: '/query'
  },
  {
    path: '/query',
    name: 'query',
    component: () => import('../views/QueryView.vue'),
    meta: { title: 'Query' }
  },
  {
    path: '/databases',
    name: 'databases',
    component: () => import('../views/DatabaseView.vue'),
    meta: { title: 'Databases' }
  },
  {
    path: '/history',
    name: 'history',
    component: () => import('../views/HistoryView.vue'),
    meta: { title: 'History' }
  }
]

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes
})

router.beforeEach((to, _from, next) => {
  document.title = `${to.meta.title || 'KFMS'} - Knowledge Flow Management System`
  next()
})

export default router
```

- [ ] **Step 5: 세 뷰에서 헤더 제거**

각 뷰에서 `el-container`/`el-header`/`el-main` 껍데기와 "Home" 버튼을 걷어내고 내용만 남긴다. 셸이 이미 헤더와 패딩을 제공한다.

`QueryView.vue` 템플릿을 아래로 교체 (스크립트의 `HomeFilled` import도 삭제):

```vue
<template>
  <div class="query-view">
    <QueryInput />
    <SQLPreview />

    <ResultTable v-if="queryStore.queryResults" :results="queryStore.queryResults" />

    <ResultChart
      v-if="queryStore.queryResults && queryStore.queryResults.results.length > 0"
      :data="queryStore.queryResults.results"
    />

    <el-card v-if="!queryStore.queryResults" class="help-card">
      <template #header>
        <span>💡 Example Questions</span>
      </template>
      <ul class="examples">
        <li>"카테고리별 총 매출을 보여줘"</li>
        <li>"월별 매출 추이를 보여줘"</li>
        <li>"30대 고객의 총 구매 금액은?"</li>
        <li>"가장 많이 구매한 고객 TOP 5"</li>
      </ul>
      <el-alert type="info" :closable="false" show-icon>
        <template #title>
          질문을 SQL로 변환한 뒤, 실행 전에 확인을 거칩니다.
        </template>
      </el-alert>
    </el-card>
  </div>
</template>
```

`.query-view`의 scoped 스타일도 아래로 교체하고, `.header`·`.header-content`·`.back-link`·`.content` 규칙은 삭제한다:

```css
.query-view {
  display: flex;
  flex-direction: column;
  gap: 20px;
}
```

`DatabaseView.vue`를 아래로 교체:

```vue
<template>
  <div class="database-view">
    <DatabaseManager />
  </div>
</template>

<script setup lang="ts">
import DatabaseManager from '../components/database/DatabaseManager.vue'
</script>

<style scoped>
.database-view {
  display: flex;
  flex-direction: column;
  gap: 20px;
}
</style>
```

`HistoryView.vue`를 아래로 교체:

```vue
<template>
  <div class="history-view">
    <HistoryList />
  </div>
</template>

<script setup lang="ts">
import HistoryList from '../components/history/HistoryList.vue'
</script>

<style scoped>
.history-view {
  display: flex;
  flex-direction: column;
  gap: 20px;
}
</style>
```

세 뷰 모두에서 `max-width: 1400px` 제약이 사라지는 것이 의도된 결과다 — 넓은 화면에서 본문이 좌우로 비던 문제를 없앤다.

- [ ] **Step 6: `HomeView.vue` 삭제**

```bash
git rm frontend/src/views/HomeView.vue
```

- [ ] **Step 7: 타입 체크**

Run: `cd frontend && npx vue-tsc --noEmit`
Expected: 에러 없음. `HomeView` 참조가 남아 있으면 여기서 잡힌다.

- [ ] **Step 8: 브라우저 확인**

`npm run dev` 후 http://localhost:5173 에서:
- `/` 접속 시 `/query`로 리다이렉트된다
- 좌측에 상단 바 + 3개 탭이 보이고, 탭 클릭 시 URL이 바뀌며 사이드바는 그대로 유지된다
- `/history`에서 새로고침해도 이력 패널이 그대로 뜬다
- `«` 버튼으로 사이드바가 48px로 접히고, 새로고침해도 접힌 상태가 유지된다
- 각 패널에 "Home" 버튼과 중복 제목이 더 이상 없다

- [ ] **Step 9: 커밋**

```bash
git add frontend/src/components/layout frontend/src/App.vue frontend/src/router/index.ts frontend/src/views
git commit -m "Add persistent sidebar shell with function tabs

Replaces the card-menu home and the per-view headers, which forced
every navigation to detour through the home screen."
```

---

### Task 2: 스키마 캐시

트리가 읽을 스키마 상태를 스토어에 만든다. 이 태스크는 UI 변화가 없고 스토어 API만 넓힌다.

**Files:**
- Modify: `frontend/src/stores/database.ts`

**Interfaces:**
- Consumes: `api.databases.getSchema(connectionId)` → `SchemaInfo` (이미 `services/api.ts`에 존재)
- Produces: `databaseStore`에 다음을 추가 —
  - `schemas: Record<number, Record<string, ColumnInfo[]>>`
  - `schemaLoading: Record<number, boolean>`
  - `schemaError: Record<number, string | null>`
  - `fetchSchema(connectionId: number, force?: boolean): Promise<Record<string, ColumnInfo[]>>`
  - `invalidateSchema(connectionId: number): void`
  - `export interface ColumnInfo { name: string; type: string; nullable: boolean; default: string | null }`

- [ ] **Step 1: `ColumnInfo` 타입과 스키마 상태 추가**

`stores/database.ts` 상단 import 아래에 타입을 선언하고, `loading` ref 다음에 상태를 추가한다.

```ts
export interface ColumnInfo {
  name: string
  type: string
  nullable: boolean
  default: string | null
}
```

```ts
const schemas = ref<Record<number, Record<string, ColumnInfo[]>>>({})
const schemaLoading = ref<Record<number, boolean>>({})
const schemaError = ref<Record<number, string | null>>({})
```

- [ ] **Step 2: `fetchSchema` / `invalidateSchema` 추가**

`setActiveConnection` 아래에 넣는다.

```ts
async function fetchSchema(connectionId: number, force = false) {
  if (!force && schemas.value[connectionId]) {
    return schemas.value[connectionId]
  }

  schemaLoading.value = { ...schemaLoading.value, [connectionId]: true }
  schemaError.value = { ...schemaError.value, [connectionId]: null }

  try {
    const info = await api.databases.getSchema(connectionId)
    schemas.value = { ...schemas.value, [connectionId]: info.schema as Record<string, ColumnInfo[]> }
    return schemas.value[connectionId]
  } catch (error: any) {
    const message = error.response?.data?.detail || 'Failed to load schema'
    schemaError.value = { ...schemaError.value, [connectionId]: message }
    throw error
  } finally {
    schemaLoading.value = { ...schemaLoading.value, [connectionId]: false }
  }
}

function invalidateSchema(connectionId: number) {
  const { [connectionId]: _s, ...restSchemas } = schemas.value
  const { [connectionId]: _l, ...restLoading } = schemaLoading.value
  const { [connectionId]: _e, ...restError } = schemaError.value
  schemas.value = restSchemas
  schemaLoading.value = restLoading
  schemaError.value = restError
}
```

- [ ] **Step 3: `deleteConnection`에서 캐시 무효화**

`deleteConnection`의 `await api.databases.delete(connectionId)` 바로 다음 줄에 추가한다. 연결이 사라졌는데 스키마가 남아 있으면 트리가 유령 노드를 그린다.

```ts
      invalidateSchema(connectionId)
```

- [ ] **Step 4: 스토어 반환값에 추가**

`return { ... }` 블록의 State에 `schemas, schemaLoading, schemaError`를, Actions에 `fetchSchema, invalidateSchema`를 추가한다.

- [ ] **Step 5: 타입 체크**

Run: `cd frontend && npx vue-tsc --noEmit`
Expected: 에러 없음

- [ ] **Step 6: 커밋**

```bash
git add frontend/src/stores/database.ts
git commit -m "Cache database schemas per connection

The tree re-reads the schema on every expand otherwise, and the cache
has to drop with the connection or deleted connections leave ghost nodes."
```

---

### Task 3: 스키마 트리 (읽기 전용)

연결 → 테이블 → 컬럼 3단계 트리를 세운다. 클릭 상호작용은 Task 4에서 붙이고, 여기서는 표시와 연결 선택까지만 한다.

**Files:**
- Create: `frontend/src/components/layout/SchemaTree.vue`
- Modify: `frontend/src/components/layout/AppShell.vue` (마운트 지점 교체)

**Interfaces:**
- Consumes: Task 2의 `databaseStore.fetchSchema` / `schemaError`, 기존 `activeConnections` / `setActiveConnection`
- Produces: `SchemaTree` 컴포넌트 (props 없음). 노드 데이터는 `{ key: string; label: string; kind: 'connection' | 'table' | 'column'; connectionId: number; table?: string; meta?: string }`

- [ ] **Step 1: `SchemaTree.vue` 작성**

```vue
<template>
  <div class="schema-tree">
    <el-input
      v-model="filterText"
      size="small"
      placeholder="테이블 · 컬럼 검색"
      clearable
      class="filter"
    >
      <template #prefix><el-icon><Search /></el-icon></template>
    </el-input>

    <el-empty
      v-if="databaseStore.activeConnections.length === 0"
      :image-size="60"
      description="등록된 연결이 없습니다"
    >
      <el-button size="small" type="primary" @click="router.push({ name: 'databases' })">
        연결 추가
      </el-button>
    </el-empty>

    <el-tree
      v-else
      ref="treeRef"
      lazy
      :load="loadNode"
      :props="treeProps"
      node-key="key"
      :filter-node-method="filterNode"
      :expand-on-click-node="false"
      @node-click="onNodeClick"
    >
      <template #default="{ data }">
        <span class="node">
          <span class="node-label" :class="data.kind">{{ data.label }}</span>
          <span v-if="data.meta" class="node-meta">{{ data.meta }}</span>
        </span>
      </template>
    </el-tree>
  </div>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { Search } from '@element-plus/icons-vue'
import { useDatabaseStore, type ColumnInfo } from '../../stores/database'

export interface TreeNode {
  key: string
  label: string
  kind: 'connection' | 'table' | 'column' | 'message'
  connectionId: number
  table?: string
  meta?: string
  isLeaf?: boolean
  retry?: boolean
}

const router = useRouter()
const databaseStore = useDatabaseStore()

const treeRef = ref()
const filterText = ref('')
const treeProps = { label: 'label', isLeaf: 'isLeaf' }

watch(filterText, (v) => treeRef.value?.filter(v))

function filterNode(value: string, data: TreeNode) {
  if (!value) return true
  return data.label.toLowerCase().includes(value.toLowerCase())
}

async function loadNode(node: any, resolve: (nodes: TreeNode[]) => void) {
  // Root: connections
  if (node.level === 0) {
    resolve(
      databaseStore.activeConnections.map((c) => ({
        key: `conn-${c.id}`,
        label: c.name,
        kind: 'connection' as const,
        connectionId: c.id,
        meta: c.database,
      }))
    )
    return
  }

  const data = node.data as TreeNode

  // Connection -> tables
  if (data.kind === 'connection') {
    try {
      const schema = await databaseStore.fetchSchema(data.connectionId)
      const tables = Object.keys(schema)

      if (tables.length === 0) {
        resolve([{
          key: `empty-${data.connectionId}`,
          label: '테이블이 없습니다',
          kind: 'message' as const,
          connectionId: data.connectionId,
          isLeaf: true,
        }])
        return
      }

      resolve(
        tables.map((table) => ({
          key: `tbl-${data.connectionId}-${table}`,
          label: table,
          kind: 'table' as const,
          connectionId: data.connectionId,
          table,
        }))
      )
    } catch {
      resolve([{
        key: `err-${data.connectionId}`,
        label: '스키마를 불러올 수 없습니다 · 다시 시도',
        kind: 'message' as const,
        connectionId: data.connectionId,
        isLeaf: true,
        retry: true,
      }])
    }
    return
  }

  // Table -> columns
  if (data.kind === 'table') {
    const schema = databaseStore.schemas[data.connectionId] || {}
    const columns: ColumnInfo[] = schema[data.table!] || []
    resolve(
      columns.map((col) => ({
        key: `col-${data.connectionId}-${data.table}-${col.name}`,
        label: col.name,
        kind: 'column' as const,
        connectionId: data.connectionId,
        table: data.table,
        meta: col.type,
        isLeaf: true,
      }))
    )
    return
  }

  resolve([])
}

function onNodeClick(data: TreeNode, node: any) {
  if (data.kind === 'connection') {
    databaseStore.setActiveConnection(data.connectionId)
    return
  }

  if (data.kind === 'message' && data.retry) {
    // Re-expanding a lazy node only refetches once its loaded flag is cleared.
    const parent = node.parent
    databaseStore.invalidateSchema(data.connectionId)
    parent.loaded = false
    parent.expand()
  }
}
</script>

<style scoped>
.filter {
  margin-bottom: 8px;
}

.node {
  display: flex;
  align-items: baseline;
  gap: 6px;
  overflow: hidden;
}

.node-label {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.node-label.connection {
  font-weight: 600;
}

.node-label.message {
  color: #909399;
  font-style: italic;
}

.node-meta {
  color: #a8abb2;
  font-size: 11px;
  flex-shrink: 0;
}
</style>
```

- [ ] **Step 2: `AppShell.vue`에 트리 삽입**

`<!-- SchemaTree mount point (Task 3) -->` 주석을 `<SchemaTree />`로 바꾸고 import를 추가한다.

```ts
import SchemaTree from './SchemaTree.vue'
```

- [ ] **Step 3: 타입 체크**

Run: `cd frontend && npx vue-tsc --noEmit`
Expected: 에러 없음

- [ ] **Step 4: 브라우저 확인**

- 사이드바에 연결명(`Retail Sales DB`)이 보이고 우측에 DB명(`retail`)이 회색으로 붙는다
- 연결 노드를 펼치면 `retail_sales`가 나온다
- 테이블을 펼치면 9개 컬럼이 타입 뱃지(`date`, `character varying`, `integer`, `numeric`)와 함께 나온다
- 노드를 접었다 다시 펼칠 때 DevTools Network에 `/schema` 요청이 **다시 뜨지 않는다** (캐시 동작)
- 검색창에 `gender` 입력 시 해당 컬럼만 남는다
- 연결이 0개일 때(데이터 패널에서 연결을 모두 지운 상태) "등록된 연결이 없습니다 · [연결 추가]"가 뜨고 버튼이 데이터 패널로 이동시킨다

- [ ] **Step 5: 커밋**

```bash
git add frontend/src/components/layout
git commit -m "Add schema tree to sidebar

A text-to-SQL tool with no way to see column names pushes users to
guess them, which is how the model ended up joining unrelated tables."
```

---

### Task 4: 트리 상호작용 (삽입 · 미리보기)

컬럼 클릭으로 질문에 이름을 넣고, 테이블 더블클릭으로 100행을 미리 본다. 트리가 연결 선택기 역할을 하게 되었으므로 질문창의 드롭다운을 걷어낸다.

**Files:**
- Modify: `frontend/src/stores/query.ts`
- Modify: `frontend/src/components/layout/SchemaTree.vue`
- Modify: `frontend/src/components/query/QueryInput.vue`

**Interfaces:**
- Consumes: 기존 `api.query.execute({ question, sql, database_id, validation_approved })`
- Produces: `queryStore`에 다음을 추가 —
  - `insertIdentifier(name: string): void`
  - `previewTable(tableName: string, databaseId: number): Promise<void>`

- [ ] **Step 1: `queryStore`에 두 액션 추가**

`clearResults` 위에 넣는다.

```ts
function insertIdentifier(name: string) {
  const current = currentQuestion.value
  if (!current) {
    currentQuestion.value = name
  } else if (current.endsWith(' ')) {
    currentQuestion.value = `${current}${name}`
  } else {
    currentQuestion.value = `${current} ${name}`
  }
}

function quoteIdentifier(name: string) {
  return `"${name.replace(/"/g, '""')}"`
}

async function previewTable(tableName: string, databaseId: number) {
  loading.value = true
  const question = `[미리보기] ${tableName}`
  const sql = `SELECT * FROM ${quoteIdentifier(tableName)} LIMIT 100`

  try {
    const result = await api.query.execute({
      question,
      sql,
      database_id: databaseId,
      validation_approved: true,
    })

    if (!result.success) {
      throw new Error(result.error || 'Preview failed')
    }

    queryResults.value = {
      question,
      sql,
      results: result.results || [],
      row_count: result.row_count || 0,
      execution_time_ms: result.execution_time_ms || 0,
      history_id: result.history_id,
      warnings: result.warnings,
    }
  } catch (error: any) {
    const message = error.response?.data?.detail || error.message || 'Failed to preview table'
    ElMessage.error(message)
    throw error
  } finally {
    loading.value = false
  }
}
```

`return` 블록의 Actions에 `insertIdentifier, previewTable`을 추가한다.

- [ ] **Step 2: 트리에 클릭 핸들러 연결**

`SchemaTree.vue`의 `<el-tree>`에 `@node-dblclick="onNodeDblClick"`를 추가하고, 스크립트를 수정한다.

`onNodeClick`을 아래로 교체:

```ts
function onNodeClick(data: TreeNode) {
  if (data.kind === 'connection') {
    databaseStore.setActiveConnection(data.connectionId)
  } else if (data.kind === 'column') {
    queryStore.insertIdentifier(data.label)
    if (route.name !== 'query') router.push({ name: 'query' })
  }
}

async function onNodeDblClick(data: TreeNode) {
  if (data.kind !== 'table') return
  databaseStore.setActiveConnection(data.connectionId)
  if (route.name !== 'query') await router.push({ name: 'query' })
  await queryStore.previewTable(data.label, data.connectionId)
}
```

import에 아래를 추가:

```ts
import { useRoute } from 'vue-router'
import { useQueryStore } from '../../stores/query'
```

```ts
const route = useRoute()
const queryStore = useQueryStore()
```

- [ ] **Step 3: `QueryInput.vue`에서 `DatabaseSelector` 제거**

템플릿에서 `<DatabaseSelector />`를 지우고, 스크립트의 `import DatabaseSelector from '../database/DatabaseSelector.vue'`도 지운다. 대신 활성 연결이 없을 때 안내를 띄운다. 입력 영역 바로 위에 넣는다:

```vue
    <el-alert
      v-if="!databaseStore.activeConnection"
      type="info"
      :closable="false"
      show-icon
      title="좌측 트리에서 연결을 선택하세요"
    />
```

> `DatabaseSelector.vue` 파일 자체는 삭제하지 말 것 — `ExcelUpload.vue`가 계속 사용한다.

- [ ] **Step 4: 타입 체크**

Run: `cd frontend && npx vue-tsc --noEmit`
Expected: 에러 없음

- [ ] **Step 5: 브라우저 확인**

- 데이터 패널에서 컬럼 `gender`를 클릭하면 질의 패널로 이동하며 질문창에 `gender`가 들어간다
- 컬럼을 연속 클릭하면 공백으로 구분되어 이어 붙는다
- `retail_sales`를 더블클릭하면 100행이 표시된다
- 이력 패널에 `[미리보기] retail_sales` 항목이 생긴다
- 질문창 안에 연결 드롭다운이 더 이상 없다

- [ ] **Step 6: 커밋**

```bash
git add frontend/src/stores/query.ts frontend/src/components/layout/SchemaTree.vue frontend/src/components/query/QueryInput.vue
git commit -m "Wire tree clicks to question input and table preview

Previews go through the normal execute path, so they are recorded in
history; the question text is labelled so they stay distinguishable."
```

---

### Task 5: 결과 탭 (표 · 차트 · SQL)

세로로 쌓이던 결과를 탭으로 바꾼다. `ResultTable`과 `ResultChart`가 각자 `el-card` 헤더를 갖고 있으므로 단순히 감쌀 수 없다 — 카드 껍데기를 벗겨 탭 본문으로 만들고, 공통 메타(행 수·실행시간·CSV)는 탭 바로 올린다. `ResultTable` 안의 SQL 접기 영역은 SQL 탭과 중복이므로 제거한다.

**Files:**
- Create: `frontend/src/components/results/ResultPanel.vue`
- Modify: `frontend/src/components/results/ResultTable.vue`
- Modify: `frontend/src/components/results/ResultChart.vue`
- Modify: `frontend/src/views/QueryView.vue`

**Interfaces:**
- Consumes: `QueryResult` (from `stores/query`), 기존 `ResultTable` / `ResultChart`
- Produces: `ResultPanel` — props `{ results: QueryResult }`. `ResultTable`은 `defineExpose({ exportToCSV })`로 CSV 실행을 상위에 노출한다.

- [ ] **Step 1: `ResultTable.vue` 분해**

카드 껍데기와 쿼리 상세 접기를 걷어내고 표만 남긴다. 템플릿을 아래로 교체:

```vue
<template>
  <div class="result-table" v-if="results">
    <div class="table-container" v-if="results.results.length > 0">
      <el-table
        :data="paginatedResults"
        stripe
        border
        max-height="520"
        style="width: 100%"
      >
        <el-table-column
          v-for="column in columns"
          :key="column"
          :prop="column"
          :label="column"
          :min-width="120"
          show-overflow-tooltip
        />
      </el-table>

      <el-pagination
        v-if="results.results.length > pageSize"
        v-model:current-page="currentPage"
        v-model:page-size="pageSize"
        :page-sizes="[50, 100, 200, 500]"
        :total="results.results.length"
        layout="total, sizes, prev, pager, next, jumper"
        class="pagination"
      />
    </div>

    <el-empty v-else description="No results found" />
  </div>
</template>
```

스크립트 끝의 `exportToCSV` 함수는 그대로 두고, 그 아래에 노출을 추가한다:

```ts
defineExpose({ exportToCSV })
```

스타일에서 `.result-header`, `.meta`, `.query-details`, `.detail-section`, `.sql-display` 규칙을 삭제한다(더 이상 쓰이지 않는다). `Download` 아이콘 import도 제거한다.

- [ ] **Step 2: `ResultChart.vue` 분해**

`el-card`를 걷고 차트 타입 선택기를 차트 위 툴바로 옮긴다. 템플릿을 아래로 교체:

```vue
<template>
  <div class="result-chart">
    <div class="chart-toolbar">
      <p v-if="recommendation" class="recommendation">
        💡 {{ recommendation.reasoning }}
      </p>
      <el-radio-group v-model="selectedChartType" size="small" class="chart-controls">
        <el-radio-button value="bar">
          <el-icon><Histogram /></el-icon>
          Bar
        </el-radio-button>
        <el-radio-button value="line">
          <el-icon><TrendCharts /></el-icon>
          Line
        </el-radio-button>
        <el-radio-button value="pie">
          <el-icon><PieChart /></el-icon>
          Pie
        </el-radio-button>
      </el-radio-group>
    </div>

    <div v-if="chartOption" class="chart-container">
      <v-chart :option="chartOption" :autoresize="true" style="height: 460px" />
    </div>

    <el-empty v-else description="Cannot generate chart for this data" />
  </div>
</template>
```

스타일에서 `.chart-header` 규칙을 아래로 교체한다:

```css
.chart-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 12px;
}
```

- [ ] **Step 3: `ResultPanel.vue` 작성**

```vue
<template>
  <el-card class="result-panel">
    <template #header>
      <div class="panel-header">
        <el-tabs v-model="activeTab" class="tabs">
          <el-tab-pane label="표" name="table" />
          <el-tab-pane label="차트" name="chart" />
          <el-tab-pane label="SQL" name="sql" />
        </el-tabs>

        <div class="meta">
          <span class="stat">{{ results.row_count.toLocaleString() }} rows</span>
          <span class="stat">{{ results.execution_time_ms }}ms</span>
          <el-button size="small" @click="tableRef?.exportToCSV()">
            <el-icon><Download /></el-icon>
            CSV
          </el-button>
        </div>
      </div>
    </template>

    <el-alert
      v-if="results.warnings && results.warnings.length > 0"
      type="warning"
      :closable="false"
      show-icon
      class="warnings"
    >
      <template #title>
        <span v-for="(w, i) in results.warnings" :key="i">{{ w }}</span>
      </template>
    </el-alert>

    <ResultTable v-show="activeTab === 'table'" ref="tableRef" :results="results" />

    <ResultChart
      v-if="results.results.length > 0"
      v-show="activeTab === 'chart'"
      :data="results.results"
    />
    <el-empty v-else v-show="activeTab === 'chart'" description="차트로 그릴 데이터가 없습니다" />

    <div v-show="activeTab === 'sql'" class="sql-tab">
      <div class="sql-actions">
        <el-button size="small" @click="copySQL">
          <el-icon><CopyDocument /></el-icon>
          복사
        </el-button>
      </div>
      <pre class="sql-display">{{ results.sql }}</pre>
    </div>
  </el-card>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { Download, CopyDocument } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import type { QueryResult } from '../../stores/query'
import ResultTable from './ResultTable.vue'
import ResultChart from './ResultChart.vue'

const props = defineProps<{ results: QueryResult }>()

const activeTab = ref('table')
const tableRef = ref<InstanceType<typeof ResultTable> | null>(null)

async function copySQL() {
  try {
    await navigator.clipboard.writeText(props.results.sql)
    ElMessage.success('SQL을 복사했습니다')
  } catch {
    ElMessage.error('복사에 실패했습니다')
  }
}
</script>

<style scoped>
.panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
}

.tabs {
  flex: 1;
  margin-bottom: -18px;
}

.meta {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-shrink: 0;
}

.stat {
  color: #909399;
  font-size: 13px;
}

.warnings {
  margin-bottom: 12px;
}

.sql-actions {
  display: flex;
  justify-content: flex-end;
  margin-bottom: 8px;
}

.sql-display {
  margin: 0;
  padding: 15px;
  background: #f9fafb;
  border: 1px solid #dcdfe6;
  border-radius: 4px;
  font-family: 'Courier New', monospace;
  font-size: 13px;
  line-height: 1.6;
  overflow-x: auto;
}
</style>
```

> `v-show`를 쓰는 이유: `v-if`로 탭을 갈아끼우면 탭을 바꿀 때마다 ECharts 인스턴스와 표 페이지네이션이 초기화된다.

- [ ] **Step 4: `QueryView.vue`에서 `ResultPanel`로 교체**

템플릿의 `<ResultTable>`과 `<ResultChart>` 두 블록을 아래 하나로 바꾼다:

```vue
    <ResultPanel v-if="queryStore.queryResults" :results="queryStore.queryResults" />
```

스크립트의 `ResultTable`, `ResultChart` import를 지우고 아래로 바꾼다:

```ts
import ResultPanel from '../components/results/ResultPanel.vue'
```

- [ ] **Step 5: 타입 체크**

Run: `cd frontend && npx vue-tsc --noEmit`
Expected: 에러 없음

- [ ] **Step 6: 브라우저 확인**

"카테고리별 총 매출을 보여줘"를 실행한 뒤:
- 표 / 차트 / SQL 탭이 전환된다
- 탭 바 우측에 `3 rows`, 실행시간, CSV 버튼이 있다
- CSV 버튼이 파일을 내려받는다
- 차트 탭에서 Bar/Line/Pie 전환 후 표 탭에 갔다 돌아와도 선택이 유지된다
- SQL 탭의 복사 버튼이 동작한다
- 중복된 "Query Results" / "Data Visualization" 카드 헤더가 더 이상 없다

- [ ] **Step 7: 커밋**

```bash
git add frontend/src/components/results frontend/src/views/QueryView.vue
git commit -m "Move results into table/chart/SQL tabs

Stacking both cards under a sidebar left the content column too narrow
and the SQL buried in a collapse; each view now gets the full width."
```

---

### Task 6: Excel 진입점

만들어져 있으나 어떤 뷰도 마운트하지 않아 도달할 수 없던 Excel 업로드에 자리를 준다.

**Files:**
- Modify: `frontend/src/views/DatabaseView.vue`

**Interfaces:**
- Consumes: 기존 `ExcelUpload.vue` (props 없음, 내부에서 `DatabaseSelector` 사용)
- Produces: 없음 (마지막 태스크)

- [ ] **Step 1: `DatabaseView.vue`에 `ExcelUpload` 추가**

Task 1에서 헤더를 걷어낸 상태의 템플릿을 아래로 교체한다:

```vue
<template>
  <div class="database-view">
    <DatabaseManager />
    <ExcelUpload />
  </div>
</template>
```

스크립트에 import를 추가:

```ts
import ExcelUpload from '../components/excel/ExcelUpload.vue'
```

스타일:

```css
.database-view {
  display: flex;
  flex-direction: column;
  gap: 20px;
}
```

- [ ] **Step 2: 타입 체크**

Run: `cd frontend && npx vue-tsc --noEmit`
Expected: 에러 없음

- [ ] **Step 3: 브라우저 확인**

- 데이터 패널에 연결 관리 카드 아래로 Excel 업로드 영역이 보인다
- 업로드 영역 안의 연결 선택 드롭다운이 동작한다
- `.xlsx` 파일을 올리면 업로드가 진행되고 목록에 뜬다

> 업로드가 실패하면 백엔드 `/excel/upload` 문제일 수 있다. 이 계획은 프론트엔드 범위이므로, 실패 시 고치지 말고 증상을 보고할 것.

- [ ] **Step 4: 최종 전체 확인**

스펙의 검증 항목을 훑는다:
- `/` → 질의 패널 리다이렉트
- 세 패널 전환 시 사이드바 유지, 새로고침 후 같은 패널
- 트리 펼침·검색·캐시
- 컬럼 삽입 / 테이블 미리보기
- 결과 3개 탭 + CSV
- 이력의 "재실행" → 질의 패널로 이동하며 질문 적재
- Excel 업로드 도달 가능
- 사이드바 접기 상태 유지
- 1280px·1920px 폭 레이아웃

- [ ] **Step 5: 커밋**

```bash
git add frontend/src/views/DatabaseView.vue
git commit -m "Mount Excel upload in the data panel

The component and its API were built but no view imported it, so the
feature was unreachable from the UI."
```

---

## 완료 기준

- `npx vue-tsc --noEmit` 통과
- 스펙의 검증 항목 11개 모두 확인
- `HomeView.vue` 삭제, `DatabaseSelector.vue` 보존
- `backend/` 무변경
