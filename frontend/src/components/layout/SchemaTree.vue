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

    <!-- A lazy tree loads its roots once; keying it on the connections makes a
         rename or (de)activation show up without a page reload. -->
    <el-tree
      v-else
      ref="treeRef"
      :key="connectionsKey"
      lazy
      :load="loadNode"
      :props="treeProps"
      node-key="key"
      :filter-node-method="filterNode"
      :expand-on-click-node="false"
      @node-click="onNodeClick"
    >
      <template #default="{ data }">
        <!-- el-tree emits no node-dblclick, so the handler lives on the slot
             content; .node stretches to the full row so a double-click
             anywhere in it counts, not only on the label. -->
        <span class="node" :title="data.title" @dblclick="onNodeDblClick(data)">
          <span class="node-label" :class="[data.kind, { excluded: data.excluded }]">{{ data.label }}</span>
          <span v-if="data.excluded" class="excluded-tag">분석 제외</span>
          <span v-if="data.name" class="node-name">{{ data.name }}</span>
          <span v-if="data.meta" class="node-meta">{{ data.meta }}</span>
        </span>
      </template>
    </el-tree>
  </div>
</template>

<script setup lang="ts">
import { ref, watch, computed } from 'vue'
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
  /** A column's real name when its label is the business name instead. */
  name?: string
  title?: string
  meta?: string
  /** A table left out of text-to-SQL analysis. */
  excluded?: boolean
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

const connectionsKey = computed(() =>
  databaseStore.activeConnections.map((c) => `${c.id}:${c.name}:${c.database}`).join('|') +
    `#${databaseStore.schemaVersion}`
)

const KIND_LABELS: Record<string, string> = {
  table: '테이블',
  view: '뷰',
  materialized_view: '구체화 뷰',
  foreign_table: '외부 테이블',
}

function filterNode(value: string, data: TreeNode) {
  if (!value) return true
  const needle = value.toLowerCase()
  // Match the shown name (승인금액), the column name (appramt) or the full
  // workbook name (공급가액[승인금액,현지금액]).
  return [data.label, data.name, data.title].some((s) => s?.toLowerCase().includes(needle))
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

      const infos = databaseStore.tableInfos[data.connectionId] || {}
      resolve(
        tables.map((table) => {
          const info = infos[table]
          return {
            key: `tbl-${data.connectionId}-${table}`,
            label: table,
            kind: 'table' as const,
            connectionId: data.connectionId,
            table,
            // The table's description (승인내역 테이블) beside its name.
            meta: info?.comment || undefined,
            title: [KIND_LABELS[info?.kind || 'table'], info?.comment, info?.excluded ? '분석 제외 — 질문에 쓰이지 않음' : '']
              .filter(Boolean)
              .join(' · '),
            excluded: info?.excluded,
          }
        })
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
        label: col.label || col.comment || col.name,
        name: col.label || col.comment ? col.name : undefined,
        // The full workbook name when the label is a shortened one.
        title: col.comment || undefined,
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
    // SQL needs the real name, not the Korean label shown in the tree.
    queryStore.insertIdentifier(data.name || data.label)
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
  /* Fill the row so the double-click target is the whole line, not just the
     text: el-tree has no node-dblclick event to bind at the row level. */
  flex: 1;
  min-width: 0;
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

.node-label.excluded {
  color: #a8abb2;
}

.excluded-tag {
  padding: 0 5px;
  border-radius: 8px;
  background: #f0f2f5;
  color: #8a94a3;
  font-size: 10.5px;
  flex-shrink: 0;
}

.node-label.message {
  color: #909399;
  font-style: italic;
}

/* In a narrow panel the business name is what the user reads, so it keeps its
   width and the data type gives way first. */
.node-label.column {
  flex-shrink: 0;
  max-width: 65%;
}

.node-name {
  color: #7a8494;
  font-size: 11px;
  flex-shrink: 0;
}

.node-meta {
  color: #a8abb2;
  font-size: 11px;
  flex-shrink: 0;
}

/* A table's description gives way before its name does. */
.node-label.table ~ .node-meta,
.node-name + .node-meta {
  flex-shrink: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
</style>
