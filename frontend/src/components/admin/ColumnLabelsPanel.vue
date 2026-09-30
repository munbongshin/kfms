<template>
  <div class="labels">
    <p class="intro">
      결과 표와 스키마 트리에 보이는 <b>한글 컬럼명</b>을 여기서 관리합니다. 정하지 않은 컬럼은 DB의
      <b>COMMENT(설명)</b>가 그대로 쓰이고, 여기서 정한 이름이 있으면 그것이 우선합니다. 이름은 <b>컬럼명 기준</b>이라
      한 번 정하면 같은 이름을 쓰는 모든 테이블·뷰에 적용되고, 특정 테이블만 다르게 부르고 싶을 때만 <b>테이블별 예외</b>를 추가합니다.
      LLM에게 보내는 컬럼 설명에도 같은 이름이 쓰입니다.
    </p>

    <div class="bar">
      <span class="field">
        연결
        <el-select v-model="connectionId" size="small" style="width: 200px" @change="load">
          <el-option v-for="c in databaseStore.activeConnections" :key="c.id" :label="c.name" :value="c.id" />
        </el-select>
      </span>
      <el-input v-model="filter" size="small" clearable placeholder="컬럼명 · 한글명 · 테이블 검색" style="width: 240px" />
      <el-checkbox v-model="onlyUnmapped" size="small">미매핑만 ({{ summary.unmapped }})</el-checkbox>
      <span class="spacer" />
      <button class="btn" :disabled="!connectionId" @click="download">엑셀 내려받기</button>
      <button class="btn" :disabled="!connectionId || importing" @click="picker?.click()">
        {{ importing ? '올리는 중…' : '엑셀 올리기' }}
      </button>
      <input ref="picker" type="file" accept=".xlsx" hidden @change="upload" />
    </div>

    <div class="progress" :class="{ complete: summary.total > 0 && summary.unmapped === 0 }">
      <el-progress :percentage="percent" :stroke-width="8" :show-text="false" />
      <span>
        컬럼명 {{ summary.total }}개 중 <b>{{ summary.mapped }}개</b> 이름 있음
        <template v-if="summary.unmapped">· <em>{{ summary.unmapped }}개는 DB 설명도 없어 영문 그대로 보입니다</em></template>
      </span>
    </div>

    <el-alert
      v-if="result"
      :type="result.problems.length ? 'warning' : 'success'"
      :closable="true"
      show-icon
      class="result"
      :title="`엑셀 반영: ${result.applied}개 저장, ${result.unchanged}개는 이미 같은 이름${result.problems.length ? `, ${result.problems.length}개 건너뜀` : ''}`"
      @close="result = null"
    >
      <ul v-if="result.problems.length" class="problems">
        <li v-for="(p, i) in result.problems.slice(0, 8)" :key="i">
          <template v-if="p.row">{{ p.row }}행: </template>{{ p.reason }}
        </li>
        <li v-if="result.problems.length > 8">… 외 {{ result.problems.length - 8 }}건</li>
      </ul>
    </el-alert>

    <el-table
      v-loading="loading"
      :data="visibleRows"
      size="small"
      border
      max-height="440"
      empty-text="표시할 컬럼이 없습니다"
    >
      <el-table-column label="컬럼명" width="190" show-overflow-tooltip>
        <template #default="{ row }"><code>{{ row.name }}</code></template>
      </el-table-column>
      <el-table-column label="테이블" width="90" align="center">
        <template #default="{ row }">
          <el-tooltip :content="row.tables.join(', ') || '(이 연결에 없는 컬럼)'" placement="top">
            <span :class="{ gone: !row.tables.length }">{{ row.tables.length || '없음' }}</span>
          </el-tooltip>
        </template>
      </el-table-column>
      <el-table-column label="DB 설명 (COMMENT)" min-width="180" show-overflow-tooltip>
        <template #default="{ row }">{{ row.comment || '—' }}</template>
      </el-table-column>
      <el-table-column label="한글명" min-width="230">
        <template #default="{ row }">
          <el-input
            v-model="drafts[row.name]"
            size="small"
            :placeholder="row.comment || '한글명 입력'"
            maxlength="100"
            :class="{ custom: row.source === 'connection' }"
            @change="save(row)"
            @keyup.enter="($event.target as HTMLInputElement).blur()"
          />
        </template>
      </el-table-column>
      <el-table-column label="출처" width="96" align="center">
        <template #default="{ row }">
          <el-tag v-if="row.source === 'connection'" size="small" type="success">지정</el-tag>
          <el-tag v-else-if="row.source === 'comment'" size="small" type="info">DB 설명</el-tag>
          <el-tag v-else-if="row.source === 'name'" size="small" type="info">한글 컬럼명</el-tag>
          <el-tag v-else size="small" type="danger">없음</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="테이블별 예외" min-width="220">
        <template #default="{ row }">
          <span v-for="e in row.exceptions" :key="e.id" class="exc">
            {{ e.table_key }}: <b>{{ e.label }}</b>
            <button class="x" title="예외 삭제" @click="removeException(e.id)">×</button>
          </span>
          <button v-if="row.tables.length > 1" class="link" @click="openException(row)">+ 예외</button>
        </template>
      </el-table-column>
      <el-table-column label="" width="70" align="center">
        <template #default="{ row }">
          <button v-if="row.id" class="link danger" title="지정한 이름을 지우고 DB 설명으로 되돌립니다" @click="clear(row)">
            되돌리기
          </button>
        </template>
      </el-table-column>
    </el-table>

    <!-- A different name for one table only -->
    <el-dialog v-model="exceptionOpen" title="테이블별 예외" width="420px" append-to-body>
      <p class="exc-note">
        <code>{{ exceptionRow?.name }}</code> 을(를) 선택한 테이블에서만 다른 이름으로 부릅니다.
        결과에는 컬럼명만 담겨 있어, 질문의 SQL이 읽는 테이블의 이름이 우선 쓰입니다.
      </p>
      <div class="exc-form">
        <el-select v-model="exceptionTable" placeholder="테이블" size="small">
          <el-option v-for="t in exceptionRow?.tables || []" :key="t" :label="t" :value="t" />
        </el-select>
        <el-input v-model="exceptionLabel" size="small" placeholder="한글명" maxlength="100" />
      </div>
      <template #footer>
        <el-button @click="exceptionOpen = false">취소</el-button>
        <el-button type="primary" :disabled="!exceptionTable || !exceptionLabel.trim()" @click="saveException">저장</el-button>
      </template>
    </el-dialog>

    <h4 class="terms-title">계산 컬럼 용어 <small>(모든 연결 공통)</small></h4>
    <p class="intro small">
      <code>SUM(승인금액)</code> 같은 계산 컬럼은 컬럼명에 아래 용어를 붙여 <b>승인금액 합계</b>처럼 표시합니다.
      "계산값"은 PostgreSQL이 이름을 붙이지 못한 식(<code>?column?</code>)의 이름입니다.
    </p>
    <el-table :data="terms" size="small" border>
      <el-table-column label="함수" width="140"><template #default="{ row }"><code>{{ row.func }}</code></template></el-table-column>
      <el-table-column label="기본값" width="140" prop="default" />
      <el-table-column label="표시 이름" min-width="200">
        <template #default="{ row }">
          <el-input v-model="termDrafts[row.func]" size="small" maxlength="50" :class="{ custom: row.customized }" @change="saveTerm(row)" />
        </template>
      </el-table-column>
      <el-table-column label="" width="90" align="center">
        <template #default="{ row }">
          <button v-if="row.customized" class="link" @click="resetTerm(row)">기본값으로</button>
        </template>
      </el-table-column>
    </el-table>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import {
  api,
  type ColumnLabelImportResult,
  type ColumnLabelRow,
  type ExpressionTermRow,
} from '../../services/api'
import { useDatabaseStore } from '../../stores/database'

const databaseStore = useDatabaseStore()

const connectionId = ref<number | null>(null)
const rows = ref<ColumnLabelRow[]>([])
const summary = ref({ total: 0, mapped: 0, unmapped: 0 })
const loading = ref(false)
const filter = ref('')
const onlyUnmapped = ref(false)
// What is typed in each name box, by column name; a save happens on change.
const drafts = reactive<Record<string, string>>({})

const picker = ref<HTMLInputElement | null>(null)
const importing = ref(false)
const result = ref<ColumnLabelImportResult | null>(null)

const terms = ref<ExpressionTermRow[]>([])
const termDrafts = reactive<Record<string, string>>({})

const exceptionOpen = ref(false)
const exceptionRow = ref<ColumnLabelRow | null>(null)
const exceptionTable = ref('')
const exceptionLabel = ref('')

const percent = computed(() =>
  summary.value.total ? Math.round((summary.value.mapped / summary.value.total) * 100) : 0
)

const visibleRows = computed(() => {
  const q = filter.value.trim().toLowerCase()
  return rows.value.filter((r) => {
    if (onlyUnmapped.value && r.mapped) return false
    if (!q) return true
    return [r.name, r.label, r.comment, ...r.tables].some((v) => (v || '').toLowerCase().includes(q))
  })
})

function fail(e: any, fallback: string) {
  const detail = e?.response?.data?.detail
  ElMessage.error(typeof detail === 'string' ? detail : fallback)
}

async function load() {
  if (!connectionId.value) return
  loading.value = true
  try {
    const data = await api.columnLabels.list(connectionId.value)
    // Columns still without a name come first: that is the work to do.
    rows.value = [...data.columns].sort((x, y) => Number(x.mapped) - Number(y.mapped))
    summary.value = data.summary
    for (const r of data.columns) drafts[r.name] = r.source === 'connection' ? r.label || '' : ''
  } catch (e) {
    fail(e, '컬럼 목록을 불러오지 못했습니다')
  } finally {
    loading.value = false
  }
}

/** A change is on screen everywhere at once: the tree and result tables read the store. */
async function refreshScreens() {
  if (connectionId.value) await databaseStore.reloadLabels(connectionId.value)
}

async function save(row: ColumnLabelRow) {
  if (!connectionId.value) return
  const value = (drafts[row.name] || '').trim()
  const current = row.source === 'connection' ? row.label || '' : ''
  if (value === current) return
  try {
    await api.columnLabels.set(connectionId.value, { column_name: row.name, label: value })
    await load()
    await refreshScreens()
    ElMessage.success(value ? `${row.name} → ${value}` : `${row.name}: DB 설명으로 되돌렸습니다`)
  } catch (e) {
    drafts[row.name] = current
    fail(e, '저장하지 못했습니다')
  }
}

async function clear(row: ColumnLabelRow) {
  drafts[row.name] = ''
  await save(row)
}

function openException(row: ColumnLabelRow) {
  exceptionRow.value = row
  exceptionTable.value = ''
  exceptionLabel.value = ''
  exceptionOpen.value = true
}

async function saveException() {
  if (!connectionId.value || !exceptionRow.value) return
  try {
    await api.columnLabels.set(connectionId.value, {
      column_name: exceptionRow.value.name,
      table_key: exceptionTable.value,
      label: exceptionLabel.value.trim(),
    })
    exceptionOpen.value = false
    await load()
    await refreshScreens()
    ElMessage.success('테이블별 예외를 저장했습니다')
  } catch (e) {
    fail(e, '저장하지 못했습니다')
  }
}

async function removeException(id: number) {
  if (!connectionId.value) return
  try {
    await api.columnLabels.remove(connectionId.value, id)
    await load()
    await refreshScreens()
  } catch (e) {
    fail(e, '삭제하지 못했습니다')
  }
}

async function download() {
  if (!connectionId.value) return
  try {
    const blob = await api.columnLabels.export(connectionId.value)
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `컬럼_한글명_${databaseStore.activeConnections.find((c) => c.id === connectionId.value)?.name || connectionId.value}.xlsx`
    a.click()
    URL.revokeObjectURL(url)
  } catch (e) {
    fail(e, '내려받지 못했습니다')
  }
}

async function upload(event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  input.value = ''
  if (!file || !connectionId.value) return
  importing.value = true
  try {
    result.value = await api.columnLabels.import(connectionId.value, file)
    await load()
    await refreshScreens()
  } catch (e) {
    fail(e, '엑셀을 반영하지 못했습니다')
  } finally {
    importing.value = false
  }
}

// --- computed-column terms ------------------------------------------------------------------
function takeTerms(list: ExpressionTermRow[]) {
  terms.value = list
  for (const t of list) termDrafts[t.func] = t.label
  databaseStore.loadExpressionTerms()
}

async function loadTerms() {
  try {
    takeTerms(await api.expressionTerms.list())
  } catch (e) {
    fail(e, '용어를 불러오지 못했습니다')
  }
}

async function saveTerm(row: ExpressionTermRow) {
  const value = (termDrafts[row.func] || '').trim()
  if (!value) {
    termDrafts[row.func] = row.label
    return
  }
  if (value === row.label) return
  try {
    takeTerms(await api.expressionTerms.set(row.func, value))
    ElMessage.success(`${row.func} → ${value}`)
  } catch (e) {
    termDrafts[row.func] = row.label
    fail(e, '저장하지 못했습니다')
  }
}

async function resetTerm(row: ExpressionTermRow) {
  try {
    takeTerms(await api.expressionTerms.reset(row.func))
  } catch (e) {
    fail(e, '되돌리지 못했습니다')
  }
}

onMounted(async () => {
  if (!databaseStore.connections.length) await databaseStore.fetchConnections(true)
  connectionId.value = databaseStore.activeConnectionId ?? databaseStore.activeConnections[0]?.id ?? null
  await Promise.all([load(), loadTerms()])
})

watch(() => databaseStore.activeConnectionId, (id) => {
  if (id && !connectionId.value) {
    connectionId.value = id
    load()
  }
})
</script>

<style scoped>
.intro {
  margin: 0 0 12px;
  font-size: 13px;
  line-height: 1.6;
  color: #475467;
}

.intro.small {
  margin: 4px 0 8px;
  font-size: 12.5px;
}

.bar {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 10px;
  margin-bottom: 10px;
}

.field {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  color: #344054;
}

.spacer {
  flex: 1;
}

.btn {
  padding: 5px 12px;
  border: 1px solid #b8c2d0;
  border-radius: 3px;
  background: #fff;
  font-size: 12.5px;
  color: #1f3a66;
  cursor: pointer;
}

.btn:hover:not(:disabled) {
  background: #eef3fa;
}

.btn:disabled {
  opacity: 0.5;
  cursor: default;
}

.progress {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 10px;
  font-size: 12.5px;
  color: #475467;
}

.progress :deep(.el-progress) {
  width: 200px;
}

.progress em {
  font-style: normal;
  color: #b42318;
}

.progress.complete b {
  color: #067647;
}

.result {
  margin-bottom: 10px;
}

.problems {
  margin: 4px 0 0;
  padding-left: 18px;
  font-size: 12.5px;
}

code {
  font-family: Consolas, 'Courier New', monospace;
  font-size: 12.5px;
  color: #1f3a66;
}

.gone {
  color: #b42318;
}

.custom :deep(.el-input__wrapper) {
  box-shadow: 0 0 0 1px #47a274 inset;
}

.exc {
  display: inline-flex;
  align-items: center;
  gap: 3px;
  margin-right: 8px;
  padding: 1px 6px;
  background: #f2f4f7;
  border-radius: 3px;
  font-size: 12px;
}

.exc .x {
  border: none;
  background: none;
  font-size: 14px;
  line-height: 1;
  color: #8a94a3;
  cursor: pointer;
}

.exc .x:hover {
  color: #b42318;
}

.link {
  padding: 0;
  border: none;
  background: none;
  font-size: 12.5px;
  color: #1f6fd0;
  cursor: pointer;
}

.link.danger {
  color: #b42318;
}

.exc-note {
  margin: 0 0 12px;
  font-size: 13px;
  line-height: 1.6;
  color: #475467;
}

.exc-form {
  display: flex;
  gap: 8px;
}

.terms-title {
  margin: 24px 0 0;
  font-size: 14px;
  color: #1f3a66;
}

.terms-title small {
  font-weight: 400;
  color: #8a94a3;
}
</style>
