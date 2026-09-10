<template>
  <div class="query-input">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>Ask a Question</span>
          <DatabaseSelector />
        </div>
      </template>

      <el-form>
        <el-form-item>
          <el-input
            v-model="question"
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
              :disabled="!question.trim() || !databaseStore.activeConnectionId"
            >
              <el-icon><MagicStick /></el-icon>
              Generate SQL
            </el-button>

            <el-button
              type="success"
              @click="handleExecute"
              :loading="queryStore.loading"
              :disabled="!question.trim() || !databaseStore.activeConnectionId"
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
          type="warning"
          :closable="false"
          show-icon
        >
          <template #title>
            Please select a database connection first.
            <router-link to="/databases">Manage Databases</router-link>
          </template>
        </el-alert>
      </el-form>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { MagicStick, CaretRight, RefreshLeft } from '@element-plus/icons-vue'
import { useQueryStore } from '../../stores/query'
import { useDatabaseStore } from '../../stores/database'
import DatabaseSelector from '../database/DatabaseSelector.vue'

const queryStore = useQueryStore()
const databaseStore = useDatabaseStore()

const question = ref('')

async function handleGenerate() {
  if (!databaseStore.activeConnectionId) return

  try {
    await queryStore.generateSQL(
      question.value,
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
      question.value,
      databaseStore.activeConnectionId
    )
  } catch (error) {
    // Error handled in store
  }
}

function handleClear() {
  question.value = ''
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
