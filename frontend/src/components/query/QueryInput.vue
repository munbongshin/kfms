<template>
  <div class="query-input">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>Ask a Question</span>
        </div>
      </template>

      <el-form>
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
            <el-button
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
              Generate & Execute
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
          title="좌측 트리에서 연결을 선택하세요"
        />
      </el-form>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { MagicStick, CaretRight, RefreshLeft } from '@element-plus/icons-vue'
import { useQueryStore } from '../../stores/query'
import { useDatabaseStore } from '../../stores/database'

const queryStore = useQueryStore()
const databaseStore = useDatabaseStore()

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
</style>
