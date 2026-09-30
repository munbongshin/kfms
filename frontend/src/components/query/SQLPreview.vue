<template>
  <el-dialog
    v-model="queryStore.showSQLPreview"
    :title="$t('생성된 SQL 확인')"
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
            <strong>{{ $t('⚠️ SQL이 차단되었습니다') }}</strong>
            <p>{{ $t('안전상의 이유로 이 쿼리는 실행할 수 없습니다:') }}</p>
          </div>
          <div v-else>
            <strong>{{ $t('검증 경고:') }}</strong>
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
          <span>{{ $t('생성된 SQL') }}</span>
          <el-button size="small" @click="copySQLToClipboard">
            <el-icon><CopyDocument /></el-icon>
            {{ $t('복사') }}
          </el-button>
        </div>
        <pre class="sql-code">{{ queryStore.generatedSQL }}</pre>
        <div v-if="guidance.length" class="guidance">{{ guidance.join(' · ') }}</div>
      </div>

      <!-- Question Display -->
      <div class="question-display">
        <strong>{{ $t('원래 질문:') }}</strong>
        <p>{{ queryStore.currentQuestion }}</p>
      </div>
    </div>

    <template #footer>
      <el-button @click="queryStore.cancelExecution()">{{ $t('취소') }}</el-button>
      <el-button
        v-if="queryStore.validationResult?.is_safe"
        type="primary"
        @click="handleExecute"
        :loading="queryStore.loading"
      >
        <el-icon><CaretRight /></el-icon>
        {{ $t('쿼리 실행') }}
      </el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { t } from '../../i18n'
import { computed } from 'vue'
import { CopyDocument, CaretRight } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { useQueryStore } from '../../stores/query'

const queryStore = useQueryStore()

/** What shaped this SQL, so a surprising answer can be explained. */
const guidance = computed(() => {
  const g = queryStore.generationInfo
  if (!g) return []
  const parts: string[] = []
  if (g.attempts > 1) parts.push(t('오류를 고치며 {n}번 만에 생성', { n: g.attempts }))
  if (g.examples_used) parts.push(t('북마크 예시 {n}개 참고', { n: g.examples_used }))
  if (g.terms_used.length) parts.push(t('용어 적용: {terms}', { terms: g.terms_used.join(', ') }))
  return parts
})

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
    ElMessage.success(t('SQL을 복사했습니다'))
  }
}
</script>

<style scoped>
.sql-preview {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.guidance {
  padding: 6px 12px;
  border-top: 1px solid #ebeef5;
  background: #f7f9fc;
  font-size: 12px;
  color: #6b7686;
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
