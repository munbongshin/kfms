<template>
  <nav class="function-tabs">
    <!-- Work tabs at the top; tools used now and then sit apart at the bottom. -->
    <div v-for="group in [tabs, tools]" :key="group[0].name" class="group">
      <button
        v-for="tab in group"
        :key="tab.name"
        class="tab"
        :class="{ active: route.name === tab.name }"
        :title="tab.title || tab.label"
        @click="select(tab.name)"
      >
        <el-icon><component :is="tab.icon" /></el-icon>
        <span class="label">{{ tab.label }}</span>
      </button>
    </div>
  </nav>
</template>

<script setup lang="ts">
import { useRoute, useRouter } from 'vue-router'
import { ChatLineSquare, Coin, Clock, Warning, Setting, QuestionFilled } from '@element-plus/icons-vue'

// Clicking the tab already open is reported, so the shell can fold its panel.
const emit = defineEmits<{ reselect: [name: string] }>()

const route = useRoute()
const router = useRouter()

function select(name: string) {
  if (route.name === name) emit('reselect', name)
  else router.push({ name })
}

interface Tab {
  name: string
  label: string
  icon: any
  title?: string
}

const tabs: Tab[] = [
  { name: 'query', label: '질의', icon: ChatLineSquare },
  { name: 'databases', label: '데이터', icon: Coin },
  { name: 'history', label: '이력', icon: Clock },
  { name: 'anomaly', label: '점검', icon: Warning },
]

const tools: Tab[] = [
  { name: 'settings', label: '설정', icon: Setting, title: '질문을 SQL로 바꿀 LLM 선택' },
  { name: 'help', label: '도움말', icon: QuestionFilled, title: '프로그램 구조와 사용법' },
]
</script>

<style scoped>
/* A vertical rail of icon-over-label tabs, the same on every screen. */
.function-tabs {
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  flex: 1;
}

.group {
  display: flex;
  flex-direction: column;
}

.group + .group {
  border-top: 1px solid #e4e7ed;
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
