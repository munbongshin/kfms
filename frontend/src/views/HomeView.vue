<template>
  <div class="home-view">
    <el-container>
      <el-header height="60px" class="header">
        <div class="header-content">
          <h1>KFMS</h1>
          <nav>
            <router-link to="/query">Query</router-link>
            <router-link to="/databases">Databases</router-link>
            <router-link to="/history">History</router-link>
          </nav>
        </div>
      </el-header>
      <el-main>
        <div class="welcome-section">
          <h2>Knowledge Flow Management System</h2>
          <p class="subtitle">Natural Language to SQL Query Service</p>

          <div class="features">
            <el-card class="feature-card">
              <template #header>
                <el-icon><ChatDotRound /></el-icon>
                <span>Natural Language</span>
              </template>
              <p>Ask questions in plain language, get SQL-powered answers</p>
            </el-card>

            <el-card class="feature-card">
              <template #header>
                <el-icon><Connection /></el-icon>
                <span>Multi-Database</span>
              </template>
              <p>Connect and query multiple PostgreSQL databases</p>
            </el-card>

            <el-card class="feature-card">
              <template #header>
                <el-icon><Document /></el-icon>
                <span>Excel Integration</span>
              </template>
              <p>Upload Excel files and query them like database tables</p>
            </el-card>

            <el-card class="feature-card">
              <template #header>
                <el-icon><TrendCharts /></el-icon>
                <span>Smart Visualization</span>
              </template>
              <p>LLM-recommended charts and graphs</p>
            </el-card>
          </div>

          <div class="action-buttons">
            <el-button type="primary" size="large" @click="$router.push('/query')">
              Start Querying
            </el-button>
            <el-button size="large" @click="$router.push('/databases')">
              Manage Databases
            </el-button>
          </div>

          <div class="status-check">
            <el-card>
              <template #header>
                <span>System Status</span>
              </template>
              <div v-if="healthStatus">
                <p><strong>Status:</strong> <el-tag :type="healthStatus.status === 'healthy' ? 'success' : 'danger'">{{ healthStatus.status }}</el-tag></p>
                <p><strong>Version:</strong> {{ healthStatus.version }}</p>
                <p><strong>LLM Provider:</strong> {{ healthStatus.llm_provider }}</p>
              </div>
              <div v-else>
                <p>Loading status...</p>
              </div>
            </el-card>
          </div>
        </div>
      </el-main>
    </el-container>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import axios from 'axios'
import { ChatDotRound, Connection, Document, TrendCharts } from '@element-plus/icons-vue'

interface HealthStatus {
  status: string
  app_name: string
  version: string
  llm_provider: string
  components: {
    database: string
    ollama: string
    groq: string
  }
}

const healthStatus = ref<HealthStatus | null>(null)

const checkHealth = async () => {
  try {
    const response = await axios.get('/api/v1/health')
    healthStatus.value = response.data
  } catch (error) {
    console.error('Failed to fetch health status:', error)
  }
}

onMounted(() => {
  checkHealth()
})
</script>

<style scoped>
.home-view {
  min-height: 100vh;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
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
  max-width: 1200px;
  margin: 0 auto;
  padding: 0 20px;
}

.header h1 {
  margin: 0;
  color: #667eea;
  font-size: 24px;
}

.header nav {
  display: flex;
  gap: 30px;
}

.header nav a {
  text-decoration: none;
  color: #333;
  font-weight: 500;
  transition: color 0.3s;
}

.header nav a:hover,
.header nav a.router-link-active {
  color: #667eea;
}

.welcome-section {
  max-width: 1200px;
  margin: 0 auto;
  padding: 60px 20px;
  text-align: center;
  color: white;
}

.welcome-section h2 {
  font-size: 48px;
  margin-bottom: 10px;
}

.subtitle {
  font-size: 20px;
  margin-bottom: 60px;
  opacity: 0.9;
}

.features {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
  gap: 20px;
  margin-bottom: 40px;
}

.feature-card {
  text-align: center;
}

.feature-card :deep(.el-card__header) {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
  font-weight: bold;
  font-size: 18px;
}

.action-buttons {
  margin: 40px 0;
  display: flex;
  justify-content: center;
  gap: 20px;
}

.status-check {
  max-width: 500px;
  margin: 40px auto 0;
}

.status-check :deep(.el-card__body) {
  text-align: left;
}

.status-check p {
  margin: 10px 0;
}
</style>
