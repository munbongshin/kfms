<template>
  <div class="app-shell">
    <header class="top-bar">
      <span class="brand">KFMS</span>
      <span class="top-right">
        <!-- The connection every screen works on. It lives here, not in the
             tree, because the tree is shown on the query screen only. -->
        <label class="conn-picker" title="조회할 데이터베이스 연결">
          <el-icon><Coin /></el-icon>
          <el-select
            v-model="activeConnection"
            size="small"
            placeholder="연결 선택"
            no-data-text="등록된 연결이 없습니다"
            style="width: 180px"
          >
            <el-option
              v-for="c in databaseStore.activeConnections"
              :key="c.id"
              :label="c.name"
              :value="c.id"
            />
          </el-select>
        </label>
        <button
          class="help-btn"
          :class="{ active: route.name === 'settings' }"
          title="질문을 SQL로 바꿀 LLM 선택"
          @click="router.push({ name: 'settings' })"
        >
          <el-icon><Setting /></el-icon>
          설정
        </button>
        <button
          class="help-btn"
          :class="{ active: route.name === 'help' }"
          title="프로그램 구조와 사용법"
          @click="router.push({ name: 'help' })"
        >
          <el-icon><QuestionFilled /></el-icon>
          도움말
        </button>
      </span>
    </header>

    <div class="body">
      <!-- The rail of function tabs is the same on every screen. The query
           screen opens a table panel beside it, since the tree only helps
           when asking questions. -->
      <aside class="rail">
        <FunctionTabs @reselect="onReselect" />
      </aside>

      <aside v-if="showTree && !collapsed" class="tree-panel">
        <div class="panel-head">
          <span>테이블</span>
          <button class="panel-close" title="테이블 목록 접기" @click="toggle">«</button>
        </div>
        <div class="tree-area">
          <SchemaTree />
        </div>
      </aside>

      <main class="content">
        <slot />
      </main>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Coin, QuestionFilled, Setting } from '@element-plus/icons-vue'
import FunctionTabs from './FunctionTabs.vue'
import SchemaTree from './SchemaTree.vue'
import { useDatabaseStore } from '../../stores/database'

const STORAGE_KEY = 'kfms.sidebar.collapsed'

const databaseStore = useDatabaseStore()
const route = useRoute()
const router = useRouter()
const collapsed = ref(false)

const showTree = computed(() => route.name === 'query')

const activeConnection = computed({
  get: () => databaseStore.activeConnectionId ?? undefined,
  set: (id: number | undefined) => {
    if (id) databaseStore.setActiveConnection(id)
  },
})

onMounted(() => {
  collapsed.value = localStorage.getItem(STORAGE_KEY) === 'true'
  if (databaseStore.connections.length === 0) {
    databaseStore.fetchConnections(true)
  }
})

watch(collapsed, (v) => localStorage.setItem(STORAGE_KEY, String(v)))

function toggle() {
  collapsed.value = !collapsed.value
}

/** Clicking the query tab while on it folds or unfolds its table panel. */
function onReselect(name: string) {
  if (name === 'query') toggle()
}
</script>

<style scoped>
.app-shell {
  display: flex;
  flex-direction: column;
  height: 100vh;
}

.top-bar {
  display: flex;
  align-items: center;
  gap: 12px;
  height: 44px;
  padding: 0 16px;
  background: #1b3c74;
  flex-shrink: 0;
}

.brand {
  font-weight: 700;
  font-size: 15px;
  letter-spacing: 0.5px;
  color: #fff;
}

.conn-picker {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  color: #c9d6ea;
  font-size: 14px;
}

.top-right {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-left: auto;
}

.help-btn {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  height: 26px;
  padding: 0 10px;
  border: 1px solid rgba(255, 255, 255, 0.35);
  border-radius: 3px;
  background: transparent;
  color: #fff;
  font-size: 12px;
  cursor: pointer;
}

.help-btn:hover,
.help-btn.active {
  background: rgba(255, 255, 255, 0.15);
}

.body {
  display: flex;
  flex: 1;
  min-height: 0;
}

.rail {
  width: 72px;
  flex-shrink: 0;
  background: #f7f8fa;
  border-right: 1px solid #d3dae3;
}

.tree-panel {
  display: flex;
  flex-direction: column;
  width: 250px;
  flex-shrink: 0;
  background: #fbfcfd;
  border-right: 1px solid #d3dae3;
}

.panel-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  height: 34px;
  padding: 0 6px 0 12px;
  border-bottom: 1px solid #e4e7ed;
  font-size: 12px;
  font-weight: 700;
  color: #1f3a66;
  flex-shrink: 0;
}

.panel-close {
  width: 24px;
  height: 24px;
  border: none;
  background: none;
  color: #8a94a3;
  font-size: 14px;
  cursor: pointer;
}

.panel-close:hover {
  background: #eef1f5;
  color: #1a5fa8;
}

.tree-area {
  flex: 1;
  overflow: auto;
  padding: 8px;
  min-height: 0;
}

.content {
  flex: 1;
  overflow: auto;
  padding: 12px;
  background: #f4f6f9;
  min-width: 0;
}
</style>
