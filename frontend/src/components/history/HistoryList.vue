<template>
  <div class="history-list">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>Query History</span>
          <el-button @click="refreshHistory" :loading="loading">
            <el-icon><Refresh /></el-icon>
            Refresh
          </el-button>
        </div>
      </template>

      <!-- Filters -->
      <div class="filters">
        <el-select v-model="statusFilter" placeholder="All Status" clearable style="width: 150px">
          <el-option label="Success" value="success" />
          <el-option label="Error" value="error" />
          <el-option label="Pending" value="pending" />
        </el-select>

        <el-button @click="applyFilters">
          <el-icon><Filter /></el-icon>
          Apply Filters
        </el-button>

        <el-button v-if="auth.isAdmin" type="danger" plain class="clear-all" @click="clearHistory">
          <el-icon><Delete /></el-icon>
          전체 삭제
        </el-button>
      </div>

      <!-- History Table -->
      <el-table
        :data="history"
        v-loading="loading"
        stripe
        scrollbar-always-on
        style="width: 100%"
        @row-click="viewDetail"
      >
        <el-table-column label="★" width="50">
          <template #default="{ row }">
            <el-button
              text
              size="small"
              :class="{ bookmarked: row.is_bookmarked }"
              @click.stop="toggleBookmark(row)"
            >
              <el-icon><StarFilled v-if="row.is_bookmarked" /><Star v-else /></el-icon>
            </el-button>
          </template>
        </el-table-column>

        <el-table-column prop="question" label="Question" min-width="300" show-overflow-tooltip />

        <el-table-column label="Status" width="120">
          <template #default="{ row }">
            <el-tag :type="getStatusType(row.status)">
              {{ row.status }}
            </el-tag>
          </template>
        </el-table-column>

        <el-table-column label="Rows" width="100">
          <template #default="{ row }">
            {{ row.row_count ? row.row_count.toLocaleString() : '-' }}
          </template>
        </el-table-column>

        <el-table-column label="Time" width="100">
          <template #default="{ row }">
            {{ row.execution_time_ms ? row.execution_time_ms + 'ms' : '-' }}
          </template>
        </el-table-column>

        <el-table-column label="LLM" width="120">
          <template #default="{ row }">
            {{ row.llm_provider || '-' }}
          </template>
        </el-table-column>

        <el-table-column label="Date" width="180">
          <template #default="{ row }">
            {{ formatDate(row.created_at) }}
          </template>
        </el-table-column>

        <el-table-column label="Actions" width="200" fixed="right">
          <template #default="{ row }">
            <el-button size="small" @click.stop="rerunQuery(row)">
              <el-icon><Refresh /></el-icon>
              Re-run
            </el-button>
            <el-popconfirm
              v-if="auth.isAdmin"
              title="Delete this history?"
              @confirm="deleteHistory(row.id)"
            >
              <template #reference>
                <el-button size="small" type="danger" @click.stop>
                  <el-icon><Delete /></el-icon>
                </el-button>
              </template>
            </el-popconfirm>
          </template>
        </el-table-column>
      </el-table>

      <!-- Pagination -->
      <el-pagination
        v-if="history.length >= limit"
        v-model:current-page="currentPage"
        v-model:page-size="limit"
        :page-sizes="[50, 100, 200]"
        :total="totalEstimate"
        layout="total, sizes, prev, pager, next"
        class="pagination"
        @current-change="fetchHistory"
        @size-change="fetchHistory"
      />
    </el-card>

    <!-- Detail Dialog -->
    <el-dialog v-model="showDetail" title="Query Details" width="800px">
      <div v-if="selectedHistory" class="history-detail">
        <div class="detail-section">
          <strong>Question:</strong>
          <p>{{ selectedHistory.question }}</p>
        </div>
        <div class="detail-section">
          <strong>SQL:</strong>
          <pre class="sql-display">{{ selectedHistory.generated_sql }}</pre>
        </div>
        <div v-if="selectedHistory.error_message" class="detail-section">
          <strong>Error:</strong>
          <p class="error-text">{{ selectedHistory.error_message }}</p>
        </div>
        <div class="detail-section">
          <strong>Metadata:</strong>
          <ul>
            <li>Database ID: {{ selectedHistory.database_id }}</li>
            <li>Status: {{ selectedHistory.status }}</li>
            <li>Rows: {{ selectedHistory.row_count || 0 }}</li>
            <li>Execution Time: {{ selectedHistory.execution_time_ms || 0 }}ms</li>
            <li>LLM: {{ selectedHistory.llm_provider }} ({{ selectedHistory.llm_model }})</li>
            <li>Created: {{ formatDate(selectedHistory.created_at) }}</li>
          </ul>
        </div>
      </div>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { Refresh, Filter, Delete, Star, StarFilled } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { api } from '../../services/api'
import { useQueryStore } from '../../stores/query'
import { useAuthStore } from '../../stores/auth'

const router = useRouter()
const queryStore = useQueryStore()
const auth = useAuthStore()

const history = ref<any[]>([])
const loading = ref(false)
const statusFilter = ref('')
const currentPage = ref(1)
const limit = ref(100)
const totalEstimate = ref(1000)

const showDetail = ref(false)
const selectedHistory = ref<any>(null)

function getStatusType(status: string) {
  switch (status) {
    case 'success': return 'success'
    case 'error': return 'danger'
    case 'pending': return 'info'
    default: return ''
  }
}

function formatDate(dateStr: string) {
  const date = new Date(dateStr)
  return date.toLocaleString()
}

async function fetchHistory() {
  loading.value = true
  try {
    const offset = (currentPage.value - 1) * limit.value
    history.value = await api.history.list({
      status: statusFilter.value || undefined,
      limit: limit.value,
      offset
    })
  } catch (error) {
    ElMessage.error('Failed to fetch history')
  } finally {
    loading.value = false
  }
}

function applyFilters() {
  currentPage.value = 1
  fetchHistory()
}

function refreshHistory() {
  fetchHistory()
}

async function viewDetail(row: any) {
  try {
    selectedHistory.value = await api.history.get(row.id)
    showDetail.value = true
  } catch (error) {
    ElMessage.error('Failed to load details')
  }
}

async function rerunQuery(row: any) {
  router.push('/query')
  await queryStore.runSavedSQL(row.question, row.generated_sql, Number(row.database_id))
}

async function toggleBookmark(row: any) {
  try {
    const updated = await api.history.setBookmark(row.id, !row.is_bookmarked)
    row.is_bookmarked = updated.is_bookmarked
    ElMessage.success(row.is_bookmarked ? '북마크에 추가했습니다' : '북마크를 해제했습니다')
  } catch (error) {
    ElMessage.error('Failed to update bookmark')
  }
}

async function clearHistory() {
  try {
    // Bookmarks are excluded server-side; say so plainly before deleting.
    await ElMessageBox.confirm(
      '북마크한 이력은 남기고 나머지를 모두 삭제합니다. 되돌릴 수 없습니다.',
      '이력 전체 삭제',
      { confirmButtonText: '삭제', cancelButtonText: '취소', type: 'warning' }
    )
  } catch {
    return
  }

  try {
    const result = await api.history.clear(true)
    ElMessage.success(`${result.deleted}건을 삭제했습니다. 북마크 ${result.kept}건은 유지됩니다.`)
    currentPage.value = 1
    await fetchHistory()
  } catch (error) {
    ElMessage.error('이력을 삭제하지 못했습니다')
  }
}

async function deleteHistory(historyId: number) {
  try {
    await api.history.delete(historyId)
    ElMessage.success('History deleted')
    await fetchHistory()
  } catch (error) {
    ElMessage.error('Failed to delete history')
  }
}

onMounted(() => {
  fetchHistory()
})
</script>

<style scoped>
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.filters {
  display: flex;
  gap: 10px;
  margin-bottom: 20px;
}

.clear-all {
  margin-left: auto;
}

.pagination {
  margin-top: 20px;
  display: flex;
  justify-content: center;
}

.bookmarked {
  color: #e6a23c;
}

.el-table :deep(.el-table__row) {
  cursor: pointer;
}

.history-detail {
  display: flex;
  flex-direction: column;
  gap: 20px;
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

.error-text {
  color: #f56c6c;
}

.detail-section ul {
  margin: 0;
  padding-left: 20px;
}

.detail-section li {
  margin: 5px 0;
}
</style>
