<template>
  <div class="result-table" v-if="results">
    <el-card>
      <template #header>
        <div class="result-header">
          <div>
            <h3>Query Results</h3>
            <p class="meta">
              {{ results.row_count }} rows | {{ results.execution_time_ms }}ms
            </p>
          </div>
          <div class="actions">
            <el-button size="small" @click="exportToCSV">
              <el-icon><Download /></el-icon>
              Export CSV
            </el-button>
          </div>
        </div>
      </template>

      <!-- Question & SQL Display -->
      <el-collapse class="query-details">
        <el-collapse-item title="View Query Details" name="1">
          <div class="detail-section">
            <strong>Question:</strong>
            <p>{{ results.question }}</p>
          </div>
          <div class="detail-section">
            <strong>SQL:</strong>
            <pre class="sql-display">{{ results.sql }}</pre>
          </div>
          <div v-if="results.warnings && results.warnings.length > 0" class="detail-section">
            <strong>Warnings:</strong>
            <ul>
              <li v-for="(warning, index) in results.warnings" :key="index">{{ warning }}</li>
            </ul>
          </div>
        </el-collapse-item>
      </el-collapse>

      <!-- Results Table -->
      <div class="table-container" v-if="results.results.length > 0">
        <el-table
          :data="paginatedResults"
          stripe
          border
          max-height="600"
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

        <!-- Pagination -->
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
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { Download } from '@element-plus/icons-vue'
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

  // Create CSV content
  const csvContent = [
    cols.join(','), // Header
    ...rows.map(row =>
      cols.map(col => {
        const value = row[col]
        // Escape quotes and wrap in quotes if contains comma
        const escaped = String(value).replace(/"/g, '""')
        return escaped.includes(',') ? `"${escaped}"` : escaped
      }).join(',')
    )
  ].join('\n')

  // Download
  const blob = new Blob([csvContent], { type: 'text/csv' })
  const url = window.URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `query_results_${Date.now()}.csv`
  a.click()
  window.URL.revokeObjectURL(url)
}
</script>

<style scoped>
.result-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.result-header h3 {
  margin: 0 0 5px 0;
  color: #303133;
}

.meta {
  margin: 0;
  color: #909399;
  font-size: 14px;
}

.query-details {
  margin-bottom: 20px;
}

.detail-section {
  margin-bottom: 15px;
}

.detail-section strong {
  display: block;
  margin-bottom: 5px;
  color: #606266;
}

.detail-section p {
  margin: 0;
  padding: 10px;
  background: #f5f7fa;
  border-radius: 4px;
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

.detail-section ul {
  margin: 0;
  padding-left: 20px;
  color: #e6a23c;
}

.table-container {
  margin-top: 20px;
}

.pagination {
  margin-top: 20px;
  display: flex;
  justify-content: center;
}
</style>
