/**
 * API Service Client
 * Typed Axios client for KFMS backend API
 */
import axios, { AxiosInstance } from 'axios'

// API Base URL from environment
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || '/api/v1'

// Create axios instance
const apiClient: AxiosInstance = axios.create({
  baseURL: API_BASE_URL,
  // Must outlast the backend's own budget (OLLAMA_TIMEOUT + QUERY_TIMEOUT),
  // otherwise a slow generation aborts here and hides the server's error.
  timeout: 180000,
  headers: {
    'Content-Type': 'application/json',
  },
})

// Request interceptor
apiClient.interceptors.request.use(
  (config) => {
    // Add auth token if needed (future)
    return config
  },
  (error) => {
    return Promise.reject(error)
  }
)

// Response interceptor
apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    // Handle errors globally
    console.error('API Error:', error.response?.data || error.message)
    return Promise.reject(error)
  }
)

// Type definitions
export interface DatabaseConnection {
  id: number
  name: string
  host: string
  port: number
  database: string
  username: string
  is_active: boolean
  is_read_only: boolean
  created_at: string
  updated_at: string
}

export interface DatabaseConnectionCreate {
  name: string
  host: string
  port: number
  database: string
  username: string
  password: string
  is_active?: boolean
  is_read_only?: boolean
}

export interface DatabaseConnectionUpdate {
  name?: string
  host?: string
  port?: number
  database?: string
  username?: string
  password?: string
  is_active?: boolean
  is_read_only?: boolean
}

export interface TestConnectionResponse {
  status: string
  version?: string
  database?: string
  user?: string
  error?: string
}

export interface SchemaInfo {
  connection_id: number
  connection_name: string
  schema: {
    [tableName: string]: Array<{
      name: string
      type: string
      nullable: boolean
      default: string | null
    }>
  }
}

// API Methods
export const api = {
  // Health check
  async healthCheck() {
    const response = await apiClient.get('/health')
    return response.data
  },

  // Database connections
  databases: {
    async list(activeOnly = false): Promise<DatabaseConnection[]> {
      const response = await apiClient.get('/databases', {
        params: { active_only: activeOnly }
      })
      return response.data
    },

    async create(data: DatabaseConnectionCreate): Promise<DatabaseConnection> {
      const response = await apiClient.post('/databases', data)
      return response.data
    },

    async test(connectionId: number): Promise<TestConnectionResponse> {
      const response = await apiClient.post(`/databases/${connectionId}/test`)
      return response.data
    },

    async getSchema(connectionId: number): Promise<SchemaInfo> {
      const response = await apiClient.get(`/databases/${connectionId}/schema`)
      return response.data
    },

    async delete(connectionId: number): Promise<void> {
      await apiClient.delete(`/databases/${connectionId}`)
    },
  },

  // Query operations
  query: {
    async generate(data: {
      question: string
      database_id: number
      llm_provider?: string
      context?: string
    }) {
      const response = await apiClient.post('/query/generate', data)
      return response.data
    },

    async validate(sql: string) {
      const response = await apiClient.post('/query/validate', { sql })
      return response.data
    },

    async execute(data: {
      question: string
      sql: string
      database_id: number
      llm_provider?: string
      llm_model?: string
      validation_approved?: boolean
    }) {
      const response = await apiClient.post('/query/execute', data)
      return response.data
    },

    async generateAndExecute(data: {
      question: string
      database_id: number
      llm_provider?: string
      context?: string
      auto_approve?: boolean
    }) {
      const response = await apiClient.post('/query/generate-and-execute', data)
      return response.data
    },
  },

  // Excel operations
  excel: {
    async upload(file: File, databaseId: number, ttlHours?: number) {
      const formData = new FormData()
      formData.append('file', file)
      formData.append('database_id', String(databaseId))
      if (ttlHours) {
        formData.append('ttl_hours', String(ttlHours))
      }

      const response = await apiClient.post('/excel/upload', formData, {
        headers: {
          'Content-Type': 'multipart/form-data'
        }
      })
      return response.data
    },

    async list() {
      const response = await apiClient.get('/excel/uploads')
      return response.data
    },

    async preview(uploadId: number, databaseId: number, limit = 100) {
      const response = await apiClient.get(`/excel/${uploadId}/preview`, {
        params: { database_id: databaseId, limit }
      })
      return response.data
    },

    async delete(uploadId: number, databaseId: number) {
      await apiClient.delete(`/excel/${uploadId}`, {
        params: { database_id: databaseId }
      })
    },
  },

  // History operations
  history: {
    async list(params?: {
      database_id?: string
      status?: string
      bookmarked?: boolean
      limit?: number
      offset?: number
    }) {
      const response = await apiClient.get('/history', { params })
      return response.data
    },

    async setBookmark(historyId: number, isBookmarked: boolean) {
      const response = await apiClient.patch(`/history/${historyId}/bookmark`, {
        is_bookmarked: isBookmarked,
      })
      return response.data
    },

    async get(historyId: number) {
      const response = await apiClient.get(`/history/${historyId}`)
      return response.data
    },

    async delete(historyId: number) {
      await apiClient.delete(`/history/${historyId}`)
    },

    async getStats() {
      const response = await apiClient.get('/history/stats/summary')
      return response.data
    },
  },
}

export default apiClient
