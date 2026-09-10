<template>
  <div class="database-view">
    <el-container>
      <el-header height="60px" class="header">
        <div class="header-content">
          <h2>Database Management</h2>
          <router-link to="/" class="back-link">
            <el-button><el-icon><HomeFilled /></el-icon> Home</el-button>
          </router-link>
        </div>
      </el-header>
      <el-main>
        <DatabaseManager />
      </el-main>
    </el-container>
  </div>
</template>

<script setup lang="ts">
import { HomeFilled } from '@element-plus/icons-vue'
import DatabaseManager from '../components/database/DatabaseManager.vue'
</script>

<style scoped>
.database-view {
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
  max-width: 1200px;
  margin: 0 auto;
}

.header h2 {
  margin: 0;
  color: #303133;
}

.back-link {
  text-decoration: none;
}
</style>
