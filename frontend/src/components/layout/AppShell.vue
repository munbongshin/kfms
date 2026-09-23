<template>
  <div class="app-shell">
    <header class="top-bar">
      <span class="brand">KFMS</span>
      <span v-if="databaseStore.activeConnection" class="active-conn">
        <el-tag size="small" type="success">
          {{ databaseStore.activeConnection.name }}
        </el-tag>
      </span>
    </header>

    <div class="body">
      <aside class="sidebar" :class="{ collapsed }">
        <FunctionTabs :collapsed="collapsed" />

        <div v-show="!collapsed" class="tree-area">
          <SchemaTree />
        </div>

        <button class="collapse-toggle" :title="collapsed ? '펼치기' : '접기'" @click="toggle">
          {{ collapsed ? '»' : '«' }}
        </button>
      </aside>

      <main class="content">
        <slot />
      </main>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, watch } from 'vue'
import FunctionTabs from './FunctionTabs.vue'
import SchemaTree from './SchemaTree.vue'
import { useDatabaseStore } from '../../stores/database'

const STORAGE_KEY = 'kfms.sidebar.collapsed'

const databaseStore = useDatabaseStore()
const collapsed = ref(false)

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

.active-conn {
  margin-left: auto;
}

.body {
  display: flex;
  flex: 1;
  min-height: 0;
}

.sidebar {
  position: relative;
  display: flex;
  flex-direction: column;
  width: 260px;
  background: #f7f8fa;
  border-right: 1px solid #d3dae3;
  flex-shrink: 0;
  transition: width 0.15s ease;
}

.sidebar.collapsed {
  width: 48px;
}

.tree-area {
  flex: 1;
  overflow: auto;
  padding: 8px;
  min-height: 0;
}

.collapse-toggle {
  height: 26px;
  border: none;
  border-top: 1px solid #d3dae3;
  background: #eef1f5;
  color: #909399;
  cursor: pointer;
  flex-shrink: 0;
}

.content {
  flex: 1;
  overflow: auto;
  padding: 12px;
  background: #f4f6f9;
  min-width: 0;
}
</style>
