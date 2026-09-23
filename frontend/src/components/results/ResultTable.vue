<template>
  <div class="result-table" v-if="results">
    <div v-if="preview" class="preview-bar">
      <span class="tbl">{{ preview.table }}</span>
      <el-select
        v-model="selectedColumns"
        multiple
        collapse-tags
        collapse-tags-tooltip
        size="small"
        placeholder="전체 컬럼"
        style="width: 260px"
        @visible-change="applyColumnsOnClose"
      >
        <el-option v-for="c in preview.columns" :key="c" :label="c" :value="c" />
      </el-select>
      <span class="count">{{ shownColumnCount }} / {{ preview.columns.length }} 컬럼</span>
      <button v-if="selectedColumns.length" class="link" @click="clearColumns">전체 보기</button>
    </div>

    <div class="table-container" v-if="results.results.length > 0">
      <el-table
        :data="paginatedResults"
        stripe
        border
        max-height="520"
        scrollbar-always-on
        style="width: 100%"
        @sort-change="onSortChange"
      >
        <el-table-column
          v-for="column in columns"
          :key="column"
          :prop="column"
          :label="column"
          :min-width="120"
          :sortable="preview ? 'custom' : false"
          :sort-orders="['ascending', 'descending']"
          show-overflow-tooltip
        />
      </el-table>

      <el-pagination
        v-if="preview"
        :current-page="preview.page"
        :page-size="preview.pageSize"
        :page-sizes="[50, 100, 200, 500]"
        :total="preview.total"
        layout="total, sizes, prev, pager, next, jumper"
        class="pagination"
        @current-change="reloadPage"
        @size-change="changePageSize"
      />

      <el-pagination
        v-else-if="results.results.length > pageSize"
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

<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { useQueryStore, type QueryResult } from '../../stores/query'
import { useDatabaseStore } from '../../stores/database'

const props = defineProps<{
  results: QueryResult | null
}>()

const queryStore = useQueryStore()
const databaseStore = useDatabaseStore()

// Only a table preview pages on the server; an LLM result is whatever the
// query returned, so it still pages client-side over the rows in hand.
const preview = computed(() => queryStore.preview)

const currentPage = ref(1)
const pageSize = ref(100)
const selectedColumns = ref<string[]>([])

const shownColumnCount = computed(() =>
  selectedColumns.value.length || preview.value?.columns.length || 0
)

async function reloadPage(page: number) {
  const state = preview.value
  if (!state || !databaseStore.activeConnectionId) return
  state.selected = [...selectedColumns.value]
  await queryStore.previewTable(state.table, databaseStore.activeConnectionId, page)
}

function changePageSize(size: number) {
  const state = preview.value
  if (!state) return
  state.pageSize = size
  reloadPage(1)
}

/** Reload once, when the picker closes — not on every tick, which would fire a
 *  request per column and let the responses race. */
function applyColumnsOnClose(open: boolean) {
  if (open) return
  const state = preview.value
  if (!state) return
  const same =
    state.selected.length === selectedColumns.value.length &&
    state.selected.every((c) => selectedColumns.value.includes(c))
  if (!same) reloadPage(1)
}

/** Server-side sort: the page is one slice of the table, so reordering has to
 *  happen in the query, not among the hundred rows already on screen. */
function onSortChange({ prop, order }: { prop: string; order: string | null }) {
  const state = preview.value
  if (!state || !prop) return
  state.orderBy = prop
  state.descending = order === 'descending'
  reloadPage(1)
}

function clearColumns() {
  selectedColumns.value = []
  reloadPage(1)
}

// A different table arrives with its own columns; drop the previous choice.
watch(
  () => preview.value?.table,
  () => {
    selectedColumns.value = preview.value ? [...preview.value.selected] : []
  }
)

// Extract column names from first result
const columns = computed(() => {
  if (!props.results || props.results.results.length === 0) return []
  return Object.keys(props.results.results[0])
})

// Paginated results
const paginatedResults = computed(() => {
  if (!props.results) return []
  // The server already returned exactly one page for a preview.
  if (preview.value) return props.results.results
  const start = (currentPage.value - 1) * pageSize.value
  const end = start + pageSize.value
  return props.results.results.slice(start, end)
})

// Reset pagination when results change
watch(() => props.results, () => {
  currentPage.value = 1
})

function exportToCSV() {
  if (!props.results || props.results.results.length === 0) return

  const cols = columns.value
  const rows = props.results.results

  const csvContent = [
    cols.join(','),
    ...rows.map(row =>
      cols.map(col => {
        const value = row[col]
        const escaped = String(value).replace(/"/g, '""')
        return escaped.includes(',') ? `"${escaped}"` : escaped
      }).join(',')
    )
  ].join('\n')

  const blob = new Blob([csvContent], { type: 'text/csv' })
  const url = window.URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `query_results_${Date.now()}.csv`
  a.click()
  window.URL.revokeObjectURL(url)
}

defineExpose({ exportToCSV })
</script>

<style scoped>
.pagination {
  margin-top: 20px;
  display: flex;
  justify-content: center;
}

.preview-bar {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 10px;
  padding: 8px 10px;
  background: #f7f9fc;
  border: 1px solid #d3dae3;
  font-size: 12px;
}

.preview-bar .tbl {
  font-weight: 700;
  color: #1b3c74;
}

.preview-bar .count {
  color: #6b7686;
}

.preview-bar .link {
  padding: 0;
  border: none;
  background: none;
  color: #1a5fa8;
  font-size: 12px;
  text-decoration: underline;
  cursor: pointer;
}
</style>
