<template>
  <el-dialog
    v-model="queryStore.showSQLPreview"
    title="Review Generated SQL"
    width="800px"
    :close-on-click-modal="false"
  >
    <div class="sql-preview">
      <!-- Validation Warnings -->
      <el-alert
        v-if="queryStore.validationResult && queryStore.validationResult.warnings.length > 0"
        :type="queryStore.validationResult.is_safe ? 'warning' : 'error'"
        :closable="false"
        show-icon
      >
        <template #title>
          <div v-if="!queryStore.validationResult.is_safe">
            <strong>⚠️ SQL Blocked</strong>
            <p>This query cannot be executed due to safety concerns:</p>
          </div>
          <div v-else>
            <strong>Validation Warnings:</strong>
          </div>
        </template>
        <ul>
          <li v-for="(warning, index) in queryStore.validationResult.warnings" :key="index">
            {{ warning }}
          </li>
        </ul>
      </el-alert>

      <!-- SQL Display -->
      <div class="sql-container">
        <div class="sql-header">
          <span>Generated SQL</span>
          <el-button size="small" @click="copySQLToClipboard">
            <el-icon><CopyDocument /></el-icon>
            Copy
          </el-button>
        </div>
        <pre class="sql-code">{{ queryStore.generatedSQL }}</pre>
      </div>

      <!-- Question Display -->
      <div class="question-display">
        <strong>Original Question:</strong>
        <p>{{ queryStore.currentQuestion }}</p>
      </div>
    </div>

    <template #footer>
      <el-button @click="queryStore.cancelExecution()">Cancel</el-button>
      <el-button
        v-if="queryStore.validationResult?.is_safe"
        type="primary"
        @click="handleExecute"
        :loading="queryStore.loading"
      >
        <el-icon><CaretRight /></el-icon>
        Execute Query
      </el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { CopyDocument, CaretRight } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { useQueryStore } from '../../stores/query'

const queryStore = useQueryStore()

async function handleExecute() {
  try {
    await queryStore.executeSQL()
  } catch (error) {
    // Error handled in store
  }
}

function copySQLToClipboard() {
  if (navigator.clipboard) {
    navigator.clipboard.writeText(queryStore.generatedSQL)
    ElMessage.success('SQL copied to clipboard')
  }
}
</script>

<style scoped>
.sql-preview {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.sql-container {
  border: 1px solid #dcdfe6;
  border-radius: 4px;
  overflow: hidden;
}

.sql-header {
  background: #f5f7fa;
  padding: 10px 15px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  border-bottom: 1px solid #dcdfe6;
  font-weight: bold;
}

.sql-code {
  margin: 0;
  padding: 15px;
  background: #f9fafb;
  font-family: 'Courier New', monospace;
  font-size: 14px;
  line-height: 1.6;
  overflow-x: auto;
  color: #303133;
}

.question-display {
  padding: 15px;
  background: #f0f9ff;
  border-left: 3px solid #409eff;
  border-radius: 4px;
}

.question-display p {
  margin: 5px 0 0 0;
  color: #606266;
}

.el-alert {
  margin-bottom: 15px;
}

.el-alert ul {
  margin: 10px 0 0 20px;
}
</style>
