<template>
  <el-dialog
    :model-value="modelValue"
    :title="$t('분석 대상 테이블 — {name}', { name: connection?.name || '' })"
    width="760px"
    @update:model-value="emit('update:modelValue', $event)"
    @open="load"
  >
    <p
      class="intro"
      v-html="$th('체크한 테이블만 질문(Text-to-SQL)에 쓰입니다. 체크를 푼 테이블은 LLM에 보내지 않지만, 질의 화면의 테이블 목록과 미리보기에는 그대로 남습니다. 새로 생긴 테이블은 자동으로 분석 대상이 됩니다. <strong>뷰로 대체 가능</strong> 표시는 DB의 뷰 정의를 분석해 붙이는 권장일 뿐이며, 제외 여부는 직접 정합니다.')"
    ></p>

    <div class="toolbar">
      <el-input v-model="filter" size="small" :placeholder="$t('테이블 · 설명 검색')" clearable style="width: 240px" />
      <span class="count">{{ $t('{n} / {total} 분석 대상', { n: includedCount, total: rows.length }) }}</span>
      <button class="link" :disabled="!rows.length" @click="setAll(true)">{{ $t('모두 선택') }}</button>
      <button class="link" :disabled="!rows.length" @click="setAll(false)">{{ $t('모두 해제') }}</button>
      <button class="link refresh" :disabled="loading" :title="$t('데이터베이스에서 테이블 목록을 다시 읽습니다')" @click="load(true)">
        {{ $t('새로고침') }}
      </button>
    </div>

    <el-table
      v-loading="loading"
      :data="visibleRows"
      size="small"
      border
      max-height="420"
      :empty-text="$t('테이블이 없습니다')"
    >
      <el-table-column width="48" align="center">
        <template #header>
          <el-checkbox
            :model-value="allVisibleIncluded"
            :indeterminate="someVisibleIncluded"
            @change="(v: any) => setVisible(!!v)"
          />
        </template>
        <template #default="{ row }">
          <el-checkbox v-model="row.included" />
        </template>
      </el-table-column>
      <el-table-column :label="$t('테이블')" min-width="210">
        <template #default="{ row }">
          <span :class="{ off: !row.included }">{{ row.key }}</span>
          <!-- A suggestion only: the table may still be what a question or a
               user's own view needs, so leaving it in is the user's call. -->
          <el-tooltip
            v-if="replacedBy(row).length"
            placement="top"
            :content="$t('분석 대상인 뷰 {n}개({views})가 이 테이블의 모든 컬럼을 대신합니다. 제외하면 LLM에 보내는 내용이 줄어 조금 빨라지고, 이 테이블을 직접 분석해야 하면 그대로 두세요.', { n: replacedBy(row).length, views: replacedBy(row).join(', ') })"
          >
            <span class="suggest" :class="{ done: !row.included }">
              {{ row.included ? $t('뷰로 대체 가능 · 제외 권장') : $t('뷰로 대체됨') }}
            </span>
          </el-tooltip>
        </template>
      </el-table-column>
      <el-table-column :label="$t('종류')" width="96">
        <template #default="{ row }">{{ KIND_LABELS[row.kind] ? $t(KIND_LABELS[row.kind]) : row.kind }}</template>
      </el-table-column>
      <el-table-column :label="$t('설명')" min-width="200" show-overflow-tooltip>
        <template #default="{ row }">{{ row.comment || '—' }}</template>
      </el-table-column>
      <el-table-column :label="$t('컬럼')" width="64" align="right" prop="column_count" />
    </el-table>

    <el-alert
      v-if="rows.length && includedCount === 0"
      type="warning"
      :closable="false"
      show-icon
      class="warn"
      :title="$t('분석 대상 테이블을 하나 이상 남겨 두세요.')"
    />

    <template #footer>
      <el-button @click="emit('update:modelValue', false)">{{ $t('취소') }}</el-button>
      <el-button type="primary" :loading="saving" :disabled="!dirty || includedCount === 0" @click="save">
        {{ $t('저장') }}
      </el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { t } from '../../i18n'
import { computed, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { useDatabaseStore } from '../../stores/database'
import type { DatabaseConnection, TableInfo } from '../../services/api'

const props = defineProps<{ modelValue: boolean; connection: DatabaseConnection | null }>()
const emit = defineEmits<{ 'update:modelValue': [value: boolean] }>()

const databaseStore = useDatabaseStore()

const KIND_LABELS: Record<string, string> = {
  table: '테이블',
  view: '뷰',
  materialized_view: '구체화 뷰',
  foreign_table: '외부 테이블',
}

interface Row extends TableInfo {
  included: boolean
}

const rows = ref<Row[]>([])
const original = ref<Set<string>>(new Set())
const filter = ref('')
const loading = ref(false)
const saving = ref(false)

const visibleRows = computed(() => {
  const needle = filter.value.trim().toLowerCase()
  if (!needle) return rows.value
  return rows.value.filter((r) =>
    [r.key, r.comment].some((s) => s?.toLowerCase().includes(needle))
  )
})

const includedCount = computed(() => rows.value.filter((r) => r.included).length)

/**
 * The analysed views that together read every column of `row` — so the LLM
 * can answer from them without it. Empty when there is no such set. Worked out
 * from the database's own view dependencies, and redone as boxes are ticked.
 */
function replacedBy(row: Row): string[] {
  const views = Object.entries(row.derived_views || {}).filter(([view]) =>
    rows.value.some((r) => r.key === view && r.included)
  )
  if (!views.length) return []
  const columns = databaseStore.schemas[props.connection?.id ?? -1]?.[row.key] || []
  const read = new Set(views.flatMap(([, cols]) => cols))
  return columns.length && columns.every((c) => read.has(c.name)) ? views.map(([v]) => v) : []
}
const allVisibleIncluded = computed(() => visibleRows.value.length > 0 && visibleRows.value.every((r) => r.included))
const someVisibleIncluded = computed(() => !allVisibleIncluded.value && visibleRows.value.some((r) => r.included))

const dirty = computed(() =>
  rows.value.some((r) => r.included === original.value.has(r.key))
)

async function load(refresh = false) {
  const id = props.connection?.id
  if (!id) return
  loading.value = true
  try {
    await databaseStore.fetchSchema(id, refresh === true)
    const infos = databaseStore.tableInfos[id] || {}
    rows.value = Object.values(infos).map((t) => ({ ...t, included: !t.excluded }))
    original.value = new Set(rows.value.filter((r) => r.excluded).map((r) => r.key))
  } catch (error: any) {
    ElMessage.error(error.response?.data?.detail || t('테이블 목록을 불러오지 못했습니다'))
  } finally {
    loading.value = false
  }
}

function setAll(value: boolean) {
  rows.value.forEach((r) => (r.included = value))
}

/** The header box acts on what the search shows, not on hidden rows. */
function setVisible(value: boolean) {
  visibleRows.value.forEach((r) => (r.included = value))
}

async function save() {
  const id = props.connection?.id
  if (!id) return
  saving.value = true
  try {
    const excluded = rows.value.filter((r) => !r.included).map((r) => r.key)
    const result = await databaseStore.setExcludedTables(id, excluded)
    ElMessage.success(t('분석 대상을 저장했습니다 — {total}개 중 {n}개', { total: result.total, n: result.analysed }))
    emit('update:modelValue', false)
  } catch (error: any) {
    ElMessage.error(error.response?.data?.detail || t('저장하지 못했습니다'))
  } finally {
    saving.value = false
  }
}
</script>

<style scoped>
.intro {
  margin: 0 0 12px;
  font-size: 13px;
  line-height: 1.6;
  color: #475467;
}

.toolbar {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 10px;
}

.count {
  font-size: 12.5px;
  font-weight: 600;
  color: #1a5fa8;
}

.link {
  padding: 0;
  border: none;
  background: none;
  color: #1a5fa8;
  font-size: 12.5px;
  text-decoration: underline;
  cursor: pointer;
}

.link:disabled {
  color: #98a2b3;
  cursor: not-allowed;
}

.refresh {
  margin-left: auto;
}

.off {
  color: #a8abb2;
}

.warn {
  margin-top: 10px;
}

.suggest {
  margin-left: 6px;
  padding: 0 6px;
  border-radius: 8px;
  background: #fff4e0;
  color: #b54708;
  font-size: 11px;
  cursor: help;
}

.suggest.done {
  background: #ecfdf3;
  color: #05603a;
}
</style>
