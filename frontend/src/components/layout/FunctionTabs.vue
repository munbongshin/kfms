<template>
  <nav class="function-tabs">
    <!-- Work tabs at the top; tools used now and then sit apart at the bottom. -->
    <div v-for="(group, i) in groups" :key="i" class="group">
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
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '../../stores/auth'
import { canSee } from '../../utils/access'
import { ChatLineSquare, Coin, Clock, Warning, Setting, QuestionFilled, User, Document } from '@element-plus/icons-vue'

// Clicking the tab already open is reported, so the shell can fold its panel.
const emit = defineEmits<{ reselect: [name: string] }>()

const auth = useAuthStore()
const route = useRoute()
const router = useRouter()

const visible = (list: Tab[]) => list.filter((t) => canSee(t.roles, auth.role))
const groups = computed(() => [visible(tabs), visible(tools)])

function select(name: string) {
  if (route.name === name) emit('reselect', name)
  else router.push({ name })
}

interface Tab {
  name: string
  label: string
  icon: any
  title?: string
  /** Who sees it; everyone when omitted. */
  roles?: string[]
}

const tabs: Tab[] = [
  { name: 'query', label: '질의', icon: ChatLineSquare },
  { name: 'databases', label: '데이터', icon: Coin, roles: ['admin'] },
  { name: 'history', label: '이력', icon: Clock },
  { name: 'reports', label: '보고서', icon: Document, title: '자동 실행되는 보고서' },
  { name: 'anomaly', label: '점검', icon: Warning, roles: ['admin', 'auditor'] },
  { name: 'admin', label: '관리', icon: User, title: '사용자와 감사 로그', roles: ['admin'] },
]

const tools: Tab[] = [
  { name: 'settings', label: '설정', icon: Setting, title: 'LLM 선택과 업무 용어집', roles: ['admin'] },
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
