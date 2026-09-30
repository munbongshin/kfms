/**
 * Database Store (Pinia)
 * Manages database connections state
 */
import { t } from '../i18n'
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import {
  api,
  type TableInfo,
  type DatabaseConnection,
  type DatabaseConnectionCreate,
  type DatabaseConnectionUpdate,
  type ExpressionTermRow,
} from '../services/api'
import { ElMessage } from 'element-plus'
import { tablesReadBy } from '../utils/columnLabels'

export interface ColumnInfo {
  name: string
  type: string
  nullable: boolean
  default: string | null
  /** Business name from COMMENT ON COLUMN, e.g. 카드번호 for cardno. */
  comment: string | null
  /** What the screen shows: the administrator's name if one is set, else the comment. */
  label: string | null
  /** Where the label came from: 'table' | 'connection' | 'comment' | null. */
  label_source?: string | null
}

export const useDatabaseStore = defineStore('database', () => {
  // State
  const connections = ref<DatabaseConnection[]>([])
  const activeConnectionId = ref<number | null>(null)
  const loading = ref(false)
  const schemas = ref<Record<number, Record<string, ColumnInfo[]>>>({})
  const schemaLoading = ref<Record<number, boolean>>({})
  // Kind, description and analysis flag per table, alongside the columns.
  const tableInfos = ref<Record<number, Record<string, TableInfo>>>({})
  // Bumped when the catalog is re-read, so the lazy tree reloads its nodes.
  const schemaVersion = ref(0)
  const schemaError = ref<Record<number, string | null>>({})
  // What SUM, COUNT ... are called on computed columns (function -> name); admin-managed.
  const expressionTerms = ref<Record<string, string>>({})

  // Computed
  const activeConnection = computed(() => {
    if (!activeConnectionId.value) return null
    return connections.value.find(conn => conn.id === activeConnectionId.value) || null
  })

  const activeConnections = computed(() => {
    return connections.value.filter(conn => conn.is_active)
  })

  // Actions
  async function fetchConnections(activeOnly = false) {
    loading.value = true
    try {
      connections.value = await api.databases.list(activeOnly)

      // Set first active connection as default if none selected
      if (!activeConnectionId.value && connections.value.length > 0) {
        const firstActive = connections.value.find(conn => conn.is_active)
        if (firstActive) {
          activeConnectionId.value = firstActive.id
        }
      }
    } catch (error: any) {
      ElMessage.error(t('연결 목록을 불러오지 못했습니다'))
      console.error(error)
    } finally {
      loading.value = false
    }
  }

  async function createConnection(data: DatabaseConnectionCreate) {
    loading.value = true
    try {
      const newConnection = await api.databases.create(data)
      connections.value.push(newConnection)

      // Set as active if it's the only connection
      if (connections.value.length === 1) {
        activeConnectionId.value = newConnection.id
      }

      ElMessage.success(t('"{name}" 연결을 추가했습니다', { name: newConnection.name }))
      return newConnection
    } catch (error: any) {
      const message = error.response?.data?.detail || t('연결을 추가하지 못했습니다')
      ElMessage.error(message)
      throw error
    } finally {
      loading.value = false
    }
  }

  async function testConnection(connectionId: number) {
    loading.value = true
    try {
      const result = await api.databases.test(connectionId)

      if (result.status === 'success') {
        ElMessage.success({
          message: t('연결에 성공했습니다\n데이터베이스: {database}\n사용자: {user}', { database: result.database ?? '', user: result.user ?? '' }),
          duration: 3000
        })
      } else {
        ElMessage.error(t('연결에 실패했습니다: {error}', { error: result.error ?? '' }))
      }

      return result
    } catch (error: any) {
      ElMessage.error(t('연결을 테스트하지 못했습니다'))
      throw error
    } finally {
      loading.value = false
    }
  }

  async function updateConnection(connectionId: number, changes: DatabaseConnectionUpdate) {
    loading.value = true
    try {
      const updated = await api.databases.update(connectionId, changes)
      const index = connections.value.findIndex(conn => conn.id === connectionId)
      if (index !== -1) connections.value.splice(index, 1, updated)

      // A rename keeps the schema; anything else may point somewhere new.
      if (Object.keys(changes).some(k => k !== 'name')) invalidateSchema(connectionId)

      if (activeConnectionId.value === connectionId && !updated.is_active) {
        activeConnectionId.value = activeConnections.value[0]?.id || null
      }

      ElMessage.success(t('"{name}" 연결을 수정했습니다', { name: updated.name }))
      return updated
    } catch (error: any) {
      ElMessage.error(error.response?.data?.detail || t('연결을 수정하지 못했습니다'))
      throw error
    } finally {
      loading.value = false
    }
  }

  async function deleteConnection(connectionId: number) {
    loading.value = true
    try {
      await api.databases.delete(connectionId)
      invalidateSchema(connectionId)

      // Remove from local state
      const index = connections.value.findIndex(conn => conn.id === connectionId)
      if (index !== -1) {
        const deletedName = connections.value[index].name
        connections.value.splice(index, 1)
        ElMessage.success(t('"{name}" 연결을 삭제했습니다', { name: deletedName }))
      }

      // Clear active if it was deleted
      if (activeConnectionId.value === connectionId) {
        activeConnectionId.value = connections.value[0]?.id || null
      }
    } catch (error: any) {
      ElMessage.error(t('연결을 삭제하지 못했습니다'))
      throw error
    } finally {
      loading.value = false
    }
  }

  function setActiveConnection(connectionId: number) {
    const conn = connections.value.find(c => c.id === connectionId)
    if (conn && conn.is_active) {
      activeConnectionId.value = connectionId
    }
  }

  async function fetchSchema(connectionId: number, force = false) {
    if (!force && schemas.value[connectionId]) {
      return schemas.value[connectionId]
    }

    schemaLoading.value = { ...schemaLoading.value, [connectionId]: true }
    schemaError.value = { ...schemaError.value, [connectionId]: null }

    try {
      // force also asks the server to re-read the database, not its cache.
      const info = await api.databases.getSchema(connectionId, force)
      schemas.value = { ...schemas.value, [connectionId]: info.schema as Record<string, ColumnInfo[]> }
      tableInfos.value = { ...tableInfos.value, [connectionId]: info.tables || {} }
      return schemas.value[connectionId]
    } catch (error: any) {
      const message = error.response?.data?.detail || 'Failed to load schema'
      schemaError.value = { ...schemaError.value, [connectionId]: message }
      throw error
    } finally {
      schemaLoading.value = { ...schemaLoading.value, [connectionId]: false }
    }
  }

  /** Column name -> the name to show, for one connection. A query result carries
   *  only bare column names, so headers are labelled by name alone. When a table
   *  has its own name for a column, the tables the SQL mentions win. */
  function columnLabels(connectionId: number | null, sql = ''): Record<string, string> {
    return columnField(connectionId, (col) => col.label || col.comment, sql)
  }

  /** Load the computed-column terms; without them those headers stay as returned. */
  async function loadExpressionTerms() {
    try {
      const rows: ExpressionTermRow[] = await api.expressionTerms.list()
      expressionTerms.value = Object.fromEntries(rows.map((r) => [r.func, r.label]))
    } catch {
      // Headers just keep their raw names.
    }
  }

  /** Column name -> the full workbook name, for tooltips under a short label. */
  function columnComments(connectionId: number | null): Record<string, string> {
    return columnField(connectionId, (col) => col.comment)
  }

  function columnField(
    connectionId: number | null,
    pick: (col: ColumnInfo) => string | null,
    sql = ''
  ): Record<string, string> {
    const schema = connectionId ? schemas.value[connectionId] : undefined
    const out: Record<string, string> = {}
    // The first table to give a name wins, so the ones the SQL reads go first.
    for (const table of tablesReadBy(sql, Object.keys(schema || {}))) {
      for (const col of schema![table]) {
        const value = pick(col)
        if (value && !out[col.name]) out[col.name] = value
      }
    }
    return out
  }

  /** Pick up changed column names without re-reading the target database. */
  async function reloadLabels(connectionId: number) {
    const info = await api.databases.getSchema(connectionId, false)
    schemas.value = { ...schemas.value, [connectionId]: info.schema as Record<string, ColumnInfo[]> }
    tableInfos.value = { ...tableInfos.value, [connectionId]: info.tables || {} }
    schemaVersion.value++
  }

  /** Re-read tables from the database (new tables, changed comments). */
  async function refreshSchema(connectionId: number) {
    await fetchSchema(connectionId, true)
    schemaVersion.value++
  }

  /** Save which tables text-to-SQL leaves out, and mark them in place. */
  async function setExcludedTables(connectionId: number, excluded: string[]) {
    const result = await api.databases.setExcludedTables(connectionId, excluded)
    const infos = tableInfos.value[connectionId] || {}
    const dropped = new Set(result.excluded)
    tableInfos.value = {
      ...tableInfos.value,
      [connectionId]: Object.fromEntries(
        Object.entries(infos).map(([k, t]) => [k, { ...t, excluded: dropped.has(k) }])
      ),
    }
    schemaVersion.value++
    return result
  }

  function invalidateSchema(connectionId: number) {
    const { [connectionId]: _s, ...restSchemas } = schemas.value
    const { [connectionId]: _l, ...restLoading } = schemaLoading.value
    const { [connectionId]: _e, ...restError } = schemaError.value
    schemas.value = restSchemas
    schemaLoading.value = restLoading
    schemaError.value = restError
  }

  return {
    // State
    connections,
    activeConnectionId,
    loading,
    schemas,
    tableInfos,
    schemaVersion,
    schemaLoading,
    schemaError,
    expressionTerms,

    // Computed
    activeConnection,
    activeConnections,

    // Actions
    fetchConnections,
    createConnection,
    updateConnection,
    testConnection,
    deleteConnection,
    setActiveConnection,
    fetchSchema,
    refreshSchema,
    reloadLabels,
    setExcludedTables,
    columnLabels,
    columnComments,
    loadExpressionTerms,
    invalidateSchema,
  }
})
