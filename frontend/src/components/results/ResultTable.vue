<template>
  <div class="result-table" v-if="results">
    <div class="table-container" v-if="results.results.length > 0">
      <el-table
        :data="paginatedResults"
        stripe
        border
        max-height="520"
        scrollbar-always-on
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

<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import type { QueryResult } from '../../stores/query'

const props = defineProps<{
  results: QueryResult | null
}>()

const currentPage = ref(1)
const pageSize = ref(100)

// Extract column names from first result
const columns = computed(() => {
  if (!props.results || props.results.results.length === 0) return []
  return Object.keys(props.results.results[0])
})

// Paginated results
const paginatedResults = computed(() => {
  if (!props.results) return []
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
</style>
