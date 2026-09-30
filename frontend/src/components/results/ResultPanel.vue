<template>
  <el-card class="result-panel">
    <template #header>
      <div class="panel-header">
        <el-tabs v-model="activeTab" class="tabs">
          <el-tab-pane label="표" name="table" />
          <el-tab-pane label="차트" name="chart" />
          <el-tab-pane v-if="auth.isAdmin" label="SQL" name="sql" />
        </el-tabs>

        <div class="meta">
          <span class="stat">{{ results.row_count.toLocaleString() }} rows</span>
          <span class="stat">{{ results.execution_time_ms }}ms</span>
          <el-button v-if="canSaveReport" size="small" @click="showSave = true">
            <el-icon><Calendar /></el-icon>
            보고서로 저장
          </el-button>
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

    <!-- Mounted only while visible: ECharts reads a zero-sized container under v-show. -->
    <template v-if="activeTab === 'chart'">
      <ResultChart v-if="results.results.length > 0" :data="results.results" />
      <el-empty v-else description="차트로 그릴 데이터가 없습니다" />
    </template>

    <div v-if="auth.isAdmin" v-show="activeTab === 'sql'" class="sql-tab">
      <div class="sql-actions">
        <el-button size="small" @click="copySQL">
          <el-icon><CopyDocument /></el-icon>
          복사
        </el-button>
      </div>
      <pre class="sql-display">{{ results.sql }}</pre>
    </div>
  </el-card>

    <SaveReportDialog v-model="showSave" :question="results.question" :sql="results.sql" :history-id="results.history_id" />
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { Download, CopyDocument, Calendar } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import type { QueryResult } from '../../stores/query'
import ResultTable from './ResultTable.vue'
import ResultChart from './ResultChart.vue'
import SaveReportDialog from './SaveReportDialog.vue'
import { useQueryStore } from '../../stores/query'
import { useAuthStore } from '../../stores/auth'

const props = defineProps<{ results: QueryResult }>()

const queryStore = useQueryStore()
const auth = useAuthStore()
const showSave = ref(false)
// A table preview is browsing, not a question worth scheduling.
const canSaveReport = computed(() => !queryStore.preview && (!!props.results.sql || !!props.results.history_id))

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
