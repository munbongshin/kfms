/**
 * Database Store (Pinia)
 * Manages database connections state
 */
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { api, type DatabaseConnection, type DatabaseConnectionCreate } from '../services/api'
import { ElMessage } from 'element-plus'

export interface ColumnInfo {
  name: string
  type: string
  nullable: boolean
  default: string | null
  /** Business name from COMMENT ON COLUMN, e.g. 카드번호 for cardno. */
  comment: string | null
  /** What the screen shows: a short display name if set, else the comment. */
  label: string | null
}

export const useDatabaseStore = defineStore('database', () => {
  // State
  const connections = ref<DatabaseConnection[]>([])
  const activeConnectionId = ref<number | null>(null)
  const loading = ref(false)
  const schemas = ref<Record<number, Record<string, ColumnInfo[]>>>({})
  const schemaLoading = ref<Record<number, boolean>>({})
  const schemaError = ref<Record<number, string | null>>({})

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
      ElMessage.error('Failed to fetch database connections')
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

      ElMessage.success(`Connection "${newConnection.name}" created successfully`)
      return newConnection
    } catch (error: any) {
      const message = error.response?.data?.detail || 'Failed to create connection'
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
          message: `Connection successful!\nDatabase: ${result.database}\nUser: ${result.user}`,
          duration: 3000
        })
      } else {
        ElMessage.error(`Connection failed: ${result.error}`)
      }

      return result
    } catch (error: any) {
      ElMessage.error('Failed to test connection')
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
        ElMessage.success(`Connection "${deletedName}" deleted`)
      }

      // Clear active if it was deleted
      if (activeConnectionId.value === connectionId) {
        activeConnectionId.value = connections.value[0]?.id || null
      }
    } catch (error: any) {
      ElMessage.error('Failed to delete connection')
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
      const info = await api.databases.getSchema(connectionId)
      schemas.value = { ...schemas.value, [connectionId]: info.schema as Record<string, ColumnInfo[]> }
      return schemas.value[connectionId]
    } catch (error: any) {
      const message = error.response?.data?.detail || 'Failed to load schema'
      schemaError.value = { ...schemaError.value, [connectionId]: message }
      throw error
    } finally {
      schemaLoading.value = { ...schemaLoading.value, [connectionId]: false }
    }
  }

  /** Column name -> business name for one connection. A query result carries
   *  only bare column names, so its headers are labelled by name alone. */
  function columnLabels(connectionId: number | null): Record<string, string> {
    return columnField(connectionId, (col) => col.label || col.comment)
  }

  /** Column name -> the full workbook name, for tooltips under a short label. */
  function columnComments(connectionId: number | null): Record<string, string> {
    return columnField(connectionId, (col) => col.comment)
  }

  function columnField(
    connectionId: number | null,
    pick: (col: ColumnInfo) => string | null
  ): Record<string, string> {
    const schema = connectionId ? schemas.value[connectionId] : undefined
    const out: Record<string, string> = {}
    for (const columns of Object.values(schema || {})) {
      for (const col of columns) {
        const value = pick(col)
        if (value && !out[col.name]) out[col.name] = value
      }
    }
    return out
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
    schemaLoading,
    schemaError,

    // Computed
    activeConnection,
    activeConnections,

    // Actions
    fetchConnections,
    createConnection,
    testConnection,
    deleteConnection,
    setActiveConnection,
    fetchSchema,
    columnLabels,
    columnComments,
    invalidateSchema,
  }
})
