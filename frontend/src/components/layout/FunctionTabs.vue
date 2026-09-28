<template>
  <nav class="function-tabs">
    <button
      v-for="tab in tabs"
      :key="tab.name"
      class="tab"
      :class="{ active: route.name === tab.name }"
      :title="tab.label"
      @click="select(tab.name)"
    >
      <el-icon><component :is="tab.icon" /></el-icon>
      <span class="label">{{ tab.label }}</span>
    </button>
  </nav>
</template>

<script setup lang="ts">
import { useRoute, useRouter } from 'vue-router'
import { ChatLineSquare, Coin, Clock, Warning } from '@element-plus/icons-vue'

// Clicking the tab already open is reported, so the shell can fold its panel.
const emit = defineEmits<{ reselect: [name: string] }>()

const route = useRoute()
const router = useRouter()

function select(name: string) {
  if (route.name === name) emit('reselect', name)
  else router.push({ name })
}

const tabs = [
  { name: 'query', label: '질의', icon: ChatLineSquare },
  { name: 'databases', label: '데이터', icon: Coin },
  { name: 'history', label: '이력', icon: Clock },
  { name: 'anomaly', label: '점검', icon: Warning },
]
</script>

<style scoped>
/* A vertical rail of icon-over-label tabs, the same on every screen. */
.function-tabs {
  display: flex;
  flex-direction: column;
}

.tab {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 3px;
  padding: 12px 0 10px;
  border: none;
  border-left: 3px solid transparent;
  background: transparent;
  color: #606266;
  font-size: 12px;
  cursor: pointer;
}

.tab .el-icon {
  font-size: 18px;
}

.tab:hover {
  color: #409eff;
  background: #f0f4f9;
}

.tab.active {
  color: #409eff;
  border-left-color: #409eff;
  background: #eaf2fd;
  font-weight: 600;
}
</style>
