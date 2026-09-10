<template>
  <div class="query-view">
    <el-container>
      <el-header height="60px" class="header">
        <div class="header-content">
          <h2>Natural Language Query</h2>
          <router-link to="/" class="back-link">
            <el-button><el-icon><HomeFilled /></el-icon> Home</el-button>
          </router-link>
        </div>
      </el-header>

      <el-main>
        <div class="content">
          <!-- Query Input -->
          <QueryInput />

          <!-- SQL Preview Dialog -->
          <SQLPreview />

          <!-- Results Table -->
          <ResultTable v-if="queryStore.queryResults" :results="queryStore.queryResults" />

          <!-- Results Chart -->
          <ResultChart
            v-if="queryStore.queryResults && queryStore.queryResults.results.length > 0"
            :data="queryStore.queryResults.results"
          />

          <!-- Help Section -->
          <el-card v-if="!queryStore.queryResults" class="help-card">
            <template #header>
              <span>💡 Example Questions</span>
            </template>
            <ul class="examples">
              <li>"Show me the top 10 customers by total revenue"</li>
              <li>"What are the monthly sales for 2024?"</li>
              <li>"List all products with price greater than $100"</li>
              <li>"How many orders were placed last week?"</li>
              <li>"Find customers who made more than 5 purchases"</li>
            </ul>
            <el-alert type="info" :closable="false" show-icon>
              <template #title>
                The system will generate SQL from your question and show it for review before execution.
              </template>
            </el-alert>
          </el-card>
        </div>
      </el-main>
    </el-container>
  </div>
</template>

<script setup lang="ts">
import { onMounted } from 'vue'
import { HomeFilled } from '@element-plus/icons-vue'
import { useQueryStore } from '../stores/query'
import { useDatabaseStore } from '../stores/database'
import QueryInput from '../components/query/QueryInput.vue'
import SQLPreview from '../components/query/SQLPreview.vue'
import ResultTable from '../components/results/ResultTable.vue'
import ResultChart from '../components/results/ResultChart.vue'

const queryStore = useQueryStore()
const databaseStore = useDatabaseStore()

onMounted(() => {
  // Fetch database connections if not already loaded
  if (databaseStore.connections.length === 0) {
    databaseStore.fetchConnections(true)
  }
})
</script>

<style scoped>
.query-view {
  min-height: 100vh;
  background-color: #f5f7fa;
}

.header {
  background: white;
  box-shadow: 0 2px 4px rgba(0,0,0,0.1);
}

.header-content {
  display: flex;
  justify-content: space-between;
  align-items: center;
  height: 100%;
  max-width: 1400px;
  margin: 0 auto;
}

.header h2 {
  margin: 0;
  color: #303133;
}

.back-link {
  text-decoration: none;
}

.content {
  max-width: 1400px;
  margin: 0 auto;
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.help-card {
  margin-top: 20px;
}

.examples {
  list-style: none;
  padding: 0;
  margin: 0 0 20px 0;
}

.examples li {
  padding: 10px;
  margin: 5px 0;
  background: #f0f9ff;
  border-left: 3px solid #409eff;
  border-radius: 4px;
  font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
}
</style>
