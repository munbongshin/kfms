<template>
  <div class="schema-tree">
    <el-input
      v-model="filterText"
      size="small"
      placeholder="테이블 · 컬럼 검색"
      clearable
      class="filter"
    >
      <template #prefix><el-icon><Search /></el-icon></template>
    </el-input>

    <el-empty
      v-if="databaseStore.activeConnections.length === 0"
      :image-size="60"
      description="등록된 연결이 없습니다"
    >
      <el-button size="small" type="primary" @click="router.push({ name: 'databases' })">
        연결 추가
      </el-button>
    </el-empty>

    <el-tree
      v-else
      ref="treeRef"
      lazy
      :load="loadNode"
      :props="treeProps"
      node-key="key"
      :filter-node-method="filterNode"
      :expand-on-click-node="false"
      @node-click="onNodeClick"
    >
      <template #default="{ data }">
        <span class="node" @dblclick="onNodeDblClick(data)">
          <span class="node-label" :class="data.kind">{{ data.label }}</span>
          <span v-if="data.meta" class="node-meta">{{ data.meta }}</span>
        </span>
      </template>
    </el-tree>
  </div>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Search } from '@element-plus/icons-vue'
import { useDatabaseStore, type ColumnInfo } from '../../stores/database'
import { useQueryStore } from '../../stores/query'

export interface TreeNode {
  key: string
  label: string
  kind: 'connection' | 'table' | 'column' | 'message'
  connectionId: number
  table?: string
  meta?: string
  isLeaf?: boolean
  retry?: boolean
}

const route = useRoute()
const router = useRouter()
const databaseStore = useDatabaseStore()
const queryStore = useQueryStore()

const treeRef = ref()
const filterText = ref('')
const treeProps = { label: 'label', isLeaf: 'isLeaf' }

watch(filterText, (v) => treeRef.value?.filter(v))

function filterNode(value: string, data: TreeNode) {
  if (!value) return true
  return data.label.toLowerCase().includes(value.toLowerCase())
}

async function loadNode(node: any, resolve: (nodes: TreeNode[]) => void) {
  // Root: connections
  if (node.level === 0) {
    resolve(
      databaseStore.activeConnections.map((c) => ({
        key: `conn-${c.id}`,
        label: c.name,
        kind: 'connection' as const,
        connectionId: c.id,
        meta: c.database,
      }))
    )
    return
  }

  const data = node.data as TreeNode

  // Connection -> tables
  if (data.kind === 'connection') {
    try {
      const schema = await databaseStore.fetchSchema(data.connectionId)
      const tables = Object.keys(schema)

      if (tables.length === 0) {
        resolve([{
          key: `empty-${data.connectionId}`,
          label: '테이블이 없습니다',
          kind: 'message' as const,
          connectionId: data.connectionId,
          isLeaf: true,
        }])
        return
      }

      resolve(
        tables.map((table) => ({
          key: `tbl-${data.connectionId}-${table}`,
          label: table,
          kind: 'table' as const,
          connectionId: data.connectionId,
          table,
        }))
      )
    } catch {
      resolve([{
        key: `err-${data.connectionId}`,
        label: '스키마를 불러올 수 없습니다 · 다시 시도',
        kind: 'message' as const,
        connectionId: data.connectionId,
        isLeaf: true,
        retry: true,
      }])
    }
    return
  }

  // Table -> columns
  if (data.kind === 'table') {
    const schema = databaseStore.schemas[data.connectionId] || {}
    const columns: ColumnInfo[] = schema[data.table!] || []
    resolve(
      columns.map((col) => ({
        key: `col-${data.connectionId}-${data.table}-${col.name}`,
        label: col.name,
        kind: 'column' as const,
        connectionId: data.connectionId,
        table: data.table,
        meta: col.type,
        isLeaf: true,
      }))
    )
    return
  }

  resolve([])
}

function onNodeClick(data: TreeNode, node: any) {
  if (data.kind === 'connection') {
    databaseStore.setActiveConnection(data.connectionId)
    return
  }

  if (data.kind === 'column') {
    queryStore.insertIdentifier(data.label)
    if (route.name !== 'query') router.push({ name: 'query' })
    return
  }

  if (data.kind === 'message' && data.retry) {
    // Re-expanding a lazy node only refetches once its loaded flag is cleared.
    const parent = node.parent
    databaseStore.invalidateSchema(data.connectionId)
    parent.loaded = false
    parent.expand()
  }
}

async function onNodeDblClick(data: TreeNode) {
  if (data.kind !== 'table') return
  databaseStore.setActiveConnection(data.connectionId)
  if (route.name !== 'query') await router.push({ name: 'query' })
  try {
    await queryStore.previewTable(data.label, data.connectionId)
  } catch {
    // Error surfaced by the store
  }
}
</script>

<style scoped>
.filter {
  margin-bottom: 8px;
}

.node {
  display: flex;
  align-items: baseline;
  gap: 6px;
  overflow: hidden;
}

.node-label {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.node-label.connection {
  font-weight: 600;
}

.node-label.message {
  color: #909399;
  font-style: italic;
}

.node-meta {
  color: #a8abb2;
  font-size: 11px;
  flex-shrink: 0;
}
</style>
