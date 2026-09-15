<template>
  <nav class="function-tabs">
    <button
      v-for="tab in tabs"
      :key="tab.name"
      class="tab"
      :class="{ active: route.name === tab.name }"
      :title="tab.label"
      @click="router.push({ name: tab.name })"
    >
      <el-icon><component :is="tab.icon" /></el-icon>
      <span v-if="!collapsed" class="label">{{ tab.label }}</span>
    </button>
  </nav>
</template>

<script setup lang="ts">
import { useRoute, useRouter } from 'vue-router'
import { ChatLineSquare, Coin, Clock } from '@element-plus/icons-vue'

defineProps<{ collapsed: boolean }>()

const route = useRoute()
const router = useRouter()

const tabs = [
  { name: 'query', label: '질의', icon: ChatLineSquare },
  { name: 'databases', label: '데이터', icon: Coin },
  { name: 'history', label: '이력', icon: Clock },
]
</script>

<style scoped>
.function-tabs {
  display: flex;
  border-bottom: 1px solid #e4e7ed;
}

.tab {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  padding: 12px 4px;
  border: none;
  border-bottom: 2px solid transparent;
  background: transparent;
  color: #606266;
  font-size: 13px;
  cursor: pointer;
}

.tab:hover {
  color: #409eff;
  background: #f5f7fa;
}

.tab.active {
  color: #409eff;
  border-bottom-color: #409eff;
  font-weight: 600;
}
</style>
