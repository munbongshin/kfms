<template>
  <div class="query-input">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>Ask a Question</span>
        </div>
      </template>

      <el-form>
        <div v-if="queryStore.canFollowUp" class="follow-up">
          <el-checkbox v-model="queryStore.followUp">앞 질문에 이어서 묻기</el-checkbox>
          <span class="follow-hint">
            {{ queryStore.followUp
              ? `"${shorten(queryStore.queryResults?.question)}" 결과를 이어서 좁히거나 바꿔 물을 수 있습니다 (예: 그중 상위 5개만)`
              : '새 질문으로 처음부터 만듭니다' }}
          </span>
        </div>

        <el-form-item>
          <el-input
            v-model="queryStore.currentQuestion"
            type="textarea"
            :rows="4"
            placeholder="Example: Show me the top 10 customers by revenue this year"
            :disabled="queryStore.loading"
          />
        </el-form-item>

        <el-form-item>
          <div class="button-group">
            <!-- Only administrators see and check SQL; everyone else just asks. -->
            <el-button
              v-if="auth.isAdmin"
              type="primary"
              @click="handleGenerate"
              :loading="queryStore.loading"
              :disabled="!queryStore.currentQuestion.trim() || !databaseStore.activeConnectionId"
            >
              <el-icon><MagicStick /></el-icon>
              Generate SQL
            </el-button>

            <el-button
              type="success"
              @click="handleExecute"
              :loading="queryStore.loading"
              :disabled="!queryStore.currentQuestion.trim() || !databaseStore.activeConnectionId"
            >
              <el-icon><CaretRight /></el-icon>
              {{ auth.isAdmin ? 'Generate & Execute' : '질문하기' }}
            </el-button>

            <el-button
              @click="handleClear"
              :disabled="queryStore.loading"
            >
              <el-icon><RefreshLeft /></el-icon>
              Clear
            </el-button>
          </div>
        </el-form-item>

        <el-alert
          v-if="!databaseStore.activeConnectionId"
          type="info"
          :closable="false"
          show-icon
          title="상단의 연결 선택에서 데이터베이스를 고르세요"
        />
      </el-form>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { MagicStick, CaretRight, RefreshLeft } from '@element-plus/icons-vue'
import { useQueryStore } from '../../stores/query'
import { useDatabaseStore } from '../../stores/database'
import { useAuthStore } from '../../stores/auth'

const queryStore = useQueryStore()
const databaseStore = useDatabaseStore()
const auth = useAuthStore()

async function handleGenerate() {
  if (!databaseStore.activeConnectionId) return

  try {
    await queryStore.generateSQL(
      queryStore.currentQuestion,
      databaseStore.activeConnectionId
    )
  } catch (error) {
    // Error handled in store
  }
}

async function handleExecute() {
  if (!databaseStore.activeConnectionId) return

  try {
    await queryStore.directExecute(
      queryStore.currentQuestion,
      databaseStore.activeConnectionId
    )
  } catch (error) {
    // Error handled in store
  }
}

const shorten = (text?: string) => (text && text.length > 28 ? text.slice(0, 28) + '…' : text || '')

function handleClear() {
  queryStore.clearResults()
}
</script>

<style scoped>
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.button-group {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
}

.el-alert {
  margin-top: 10px;
}

.follow-up {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 10px;
  margin-bottom: 10px;
  padding: 6px 10px;
  background: #f7f9fc;
  border: 1px solid #d3dae3;
}

.follow-hint {
  font-size: 12px;
  color: #6b7686;
}

</style>
