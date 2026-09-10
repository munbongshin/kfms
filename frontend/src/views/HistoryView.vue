<template>
  <div class="history-view">
    <el-container>
      <el-header height="60px" class="header">
        <div class="header-content">
          <h2>Query History</h2>
          <router-link to="/" class="back-link">
            <el-button><el-icon><HomeFilled /></el-icon> Home</el-button>
          </router-link>
        </div>
      </el-header>

      <el-main>
        <div class="content">
          <HistoryList />
        </div>
      </el-main>
    </el-container>
  </div>
</template>

<script setup lang="ts">
import { HomeFilled } from '@element-plus/icons-vue'
import HistoryList from '../components/history/HistoryList.vue'
</script>

<style scoped>
.history-view {
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
}
</style>
