/**
 * API Service Client
 * Typed Axios client for KFMS backend API
 */
import axios, { AxiosInstance } from 'axios'

// API Base URL from environment
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || '/api/v1'

export const TOKEN_KEY = 'kfms.token'

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
    const token = localStorage.getItem(TOKEN_KEY)
    if (token) config.headers.Authorization = `Bearer ${token}`
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
    // An expired or revoked session: back to the sign-in screen. A failed
    // sign-in is a 401 too, but that one belongs to the form.
    const url: string = error.config?.url || ''
    if (error.response?.status === 401 && !url.startsWith('/auth/')) {
      localStorage.removeItem(TOKEN_KEY)
      if (location.pathname !== '/login') location.assign('/login')
    }
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

/** One table or view as the catalog describes it. */
export interface TableInfo {
  /** `name` in public, otherwise `schema.name` — how SQL and the LLM refer to it. */
  key: string
  schema: string
  name: string
  kind: 'table' | 'view' | 'materialized_view' | 'foreign_table'
  /** COMMENT ON TABLE, e.g. 승인내역 테이블. */
  comment: string | null
  /** Left out of text-to-SQL analysis for this connection. */
  excluded: boolean
  column_count: number
  /** Views built on this table -> the columns of this table each one reads. */
  derived_views: Record<string, string[]>
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
  tables: Record<string, TableInfo>
}

export interface Report {
  id: number
  name: string
  question: string
  sql: string
  database_id: string
  frequency: 'daily' | 'weekly' | 'monthly'
  hour: number
  weekday: number | null
  day: number | null
  is_active: boolean
  next_run_at: string | null
  last_run_at: string | null
  last_status: 'ok' | 'error' | null
  last_error: string | null
  last_row_count: number | null
  created_by: string
}

export interface NewReport {
  name: string
  question: string
  /** Empty for people who cannot see SQL: they name `history_id` instead. */
  sql?: string
  history_id?: number
  database_id: number
  frequency: string
  hour: number
  weekday?: number
  day?: number
}

export type Role = 'admin' | 'auditor' | 'viewer'

export interface AppUser {
  id: number
  username: string
  display_name: string
  role: Role
  is_active?: boolean
  created_at?: string | null
  last_login_at?: string | null
}

export interface NewUser {
  username: string
  display_name?: string
  password: string
  role?: Role
}

export interface AuthSession {
  token: string
  user: AppUser
}

export interface AuditEntry {
  id: number
  at: string
  username: string
  role: string
  action: string
  target: string
  detail: Record<string, any>
  ip: string
}

/** A business term the LLM is given when a question uses it. */
export interface AnomalySettingHistory {
  id: number
  changed_at: string
  changed_by: string
  changes: { template: string; rule: string; key: string; label: string; text: string }[]
}

export interface ColumnLabelException {
  id: number
  table_key: string
  label: string
}

/** One distinct column name on a connection, with the name it shows. */
export interface ColumnLabelRow {
  name: string
  type: string | null
  tables: string[]
  /** The DB's own comment; what shows when nobody has set a name. */
  comment: string | null
  default_label: string | null
  label: string | null
  source: 'connection' | 'comment' | null
  mapped: boolean
  /** Id of the connection-wide override, if there is one. */
  id: number | null
  exceptions: ColumnLabelException[]
}

export interface ColumnLabelList {
  columns: ColumnLabelRow[]
  tables: string[]
  summary: { total: number; mapped: number; unmapped: number }
}

export interface ColumnLabelImportResult {
  applied: number
  unchanged: number
  problems: { row: number | null; column?: string; reason: string }[]
}

export interface ExpressionTermRow {
  func: string
  label: string
  default: string
  customized: boolean
}

export interface GlossaryTerm {
  id: number
  term: string
  definition: string
}

export type LLMProviderName = 'ollama' | 'lmstudio' | 'vllm' | 'openai_compatible' | 'groq'

/** One serving platform as the server describes it — never with its API key. */
export interface LLMPlatform {
  name: LLMProviderName
  label: string
  protocol: 'ollama' | 'openai'
  description: string
  hint: string
  api_key: 'none' | 'optional' | 'required'
  fixed_base_url: boolean
  external: boolean
  default_base_url: string
  base_url: string
  model: string
  api_key_set: boolean
  api_key_hint: string | null
}

export interface LLMSettings {
  provider: LLMProviderName
  /** 'saved' once saved from the settings screen; 'env' means .env defaults. */
  source: 'saved' | 'env'
  platforms: LLMPlatform[]
}

export interface LLMProfileUpdate {
  base_url?: string
  model?: string
  /** Blank keeps the stored key. */
  api_key?: string
  clear_api_key?: boolean
}

export interface LLMSettingsUpdate {
  provider: LLMProviderName
  profiles: Partial<Record<LLMProviderName, LLMProfileUpdate>>
}

export interface LLMTestResult {
  ok: boolean
  message: string
  models?: string[]
  elapsed_ms?: number
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

    async update(connectionId: number, data: DatabaseConnectionUpdate): Promise<DatabaseConnection> {
      const response = await apiClient.patch(`/databases/${connectionId}`, data)
      return response.data
    },

    async test(connectionId: number): Promise<TestConnectionResponse> {
      const response = await apiClient.post(`/databases/${connectionId}/test`)
      return response.data
    },

    /** refresh re-reads the database catalog instead of the server's cached copy. */
    async getSchema(connectionId: number, refresh = false): Promise<SchemaInfo> {
      const response = await apiClient.get(`/databases/${connectionId}/schema`, {
        params: refresh ? { refresh: true } : undefined,
      })
      return response.data
    },

    async setExcludedTables(connectionId: number, excluded: string[]) {
      const response = await apiClient.put(`/databases/${connectionId}/excluded-tables`, { excluded })
      return response.data as { excluded: string[]; analysed: number; total: number }
    },

    async delete(connectionId: number): Promise<void> {
      await apiClient.delete(`/databases/${connectionId}`)
    },

    async readTable(connectionId: number, table: string, params: {
      columns?: string
      order_by?: string
      descending?: boolean
      limit?: number
      offset?: number
    }) {
      const response = await apiClient.get(
        `/databases/${connectionId}/tables/${encodeURIComponent(table)}/rows`,
        { params }
      )
      return response.data
    },
  },

  // Query operations
  query: {
    async generate(data: {
      question: string
      database_id: number
      llm_provider?: string
      context?: string
      previous_question?: string
      previous_sql?: string
      previous_history_id?: number
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
      previous_question?: string
      previous_sql?: string
      previous_history_id?: number
      auto_approve?: boolean
    }) {
      const response = await apiClient.post('/query/generate-and-execute', data)
      return response.data
    },

    /** Run a saved question again by its history id; the server holds the SQL,
     *  so this works for people who cannot see it. */
    async rerun(historyId: number) {
      const response = await apiClient.post(`/query/rerun/${historyId}`)
      return response.data
    },
  },

  // Excel operations
  excel: {
    async upload(file: File, databaseId: number, ttlHours?: number, tableName?: string) {
      const formData = new FormData()
      formData.append('file', file)
      formData.append('database_id', String(databaseId))
      if (tableName) {
        formData.append('table_name', tableName)
      }
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

    /** The table name an upload would get from `name`, and whether it is free. */
    async checkTableName(databaseId: number, name: string) {
      const response = await apiClient.get('/excel/table-name', {
        params: { database_id: databaseId, name },
      })
      return response.data as {
        requested: string
        name: string
        key: string
        available: boolean
        conflict_with: string | null
      }
    },

    /** Keep an upload longer; extending never shortens it. */
    async extend(uploadId: number, hours = 24) {
      const response = await apiClient.post(`/excel/${uploadId}/extend`, null, { params: { hours } })
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
  auth: {
    async status(): Promise<{ setup_required: boolean }> {
      return (await apiClient.get('/auth/status')).data
    },
    async setup(data: NewUser): Promise<AuthSession> {
      return (await apiClient.post('/auth/setup', data)).data
    },
    async login(username: string, password: string): Promise<AuthSession> {
      return (await apiClient.post('/auth/login', { username, password })).data
    },
    async me(): Promise<AppUser> {
      return (await apiClient.get('/auth/me')).data
    },
    async updateMe(data: { display_name?: string; current_password?: string; new_password?: string }): Promise<AppUser> {
      return (await apiClient.patch('/auth/me', data)).data
    },
  },

  users: {
    async list(): Promise<AppUser[]> {
      return (await apiClient.get('/users')).data
    },
    async create(data: NewUser): Promise<AppUser> {
      return (await apiClient.post('/users', data)).data
    },
    /** Whether an id is still free (compared without case). */
    async available(username: string): Promise<boolean> {
      return (await apiClient.get('/users/check', { params: { username } })).data.available
    },
    async remove(id: number): Promise<void> {
      await apiClient.delete(`/users/${id}`)
    },
    async change(id: number, data: Partial<{ display_name: string; role: Role; is_active: boolean; password: string }>): Promise<AppUser> {
      return (await apiClient.patch(`/users/${id}`, data)).data
    },
  },

  audit: {
    async list(params: { username?: string; action?: string; days?: number; limit?: number; offset?: number }): Promise<AuditEntry[]> {
      return (await apiClient.get('/audit-log', { params })).data
    },
  },

  columnLabels: {
    async list(connectionId: number): Promise<ColumnLabelList> {
      return (await apiClient.get(`/databases/${connectionId}/column-labels`)).data
    },

    /** A blank label clears the override, so the DB comment shows again. */
    async set(connectionId: number, data: { column_name: string; table_key?: string | null; label: string }) {
      return (await apiClient.put(`/databases/${connectionId}/column-labels`, data)).data
    },

    async remove(connectionId: number, id: number): Promise<void> {
      await apiClient.delete(`/databases/${connectionId}/column-labels/${id}`)
    },

    async export(connectionId: number): Promise<Blob> {
      const response = await apiClient.get(`/databases/${connectionId}/column-labels/export`, { responseType: 'blob' })
      return response.data
    },

    async import(connectionId: number, file: File): Promise<ColumnLabelImportResult> {
      const form = new FormData()
      form.append('file', file)
      return (await apiClient.post(`/databases/${connectionId}/column-labels/import`, form, {
        headers: { 'Content-Type': 'multipart/form-data' },
      })).data
    },
  },

  expressionTerms: {
    async list(): Promise<ExpressionTermRow[]> {
      return (await apiClient.get('/expression-terms')).data
    },

    async set(func: string, label: string): Promise<ExpressionTermRow[]> {
      return (await apiClient.put(`/expression-terms/${encodeURIComponent(func)}`, { label })).data
    },

    async reset(func: string): Promise<ExpressionTermRow[]> {
      return (await apiClient.delete(`/expression-terms/${encodeURIComponent(func)}`)).data
    },
  },

  glossary: {
    async list(): Promise<GlossaryTerm[]> {
      const response = await apiClient.get('/glossary')
      return response.data
    },

    async create(term: string, definition: string): Promise<GlossaryTerm> {
      const response = await apiClient.post('/glossary', { term, definition })
      return response.data
    },

    async update(id: number, term: string, definition: string): Promise<GlossaryTerm> {
      const response = await apiClient.put(`/glossary/${id}`, { term, definition })
      return response.data
    },

    async remove(id: number): Promise<void> {
      await apiClient.delete(`/glossary/${id}`)
    },
  },

  llmSettings: {
    async get(): Promise<LLMSettings> {
      const response = await apiClient.get('/llm-settings')
      return response.data
    },

    async save(data: LLMSettingsUpdate): Promise<LLMSettings> {
      const response = await apiClient.put('/llm-settings', data)
      return response.data
    },

    /** Checks the form as it stands, saved or not. */
    async test(data: LLMSettingsUpdate): Promise<LLMTestResult> {
      const response = await apiClient.post('/llm-settings/test', data)
      return response.data
    },

    /** Models offered by the chosen platform's server, per the form as it stands. */
    async models(data: LLMSettingsUpdate): Promise<string[]> {
      const response = await apiClient.post('/llm-settings/models', data)
      return response.data.models
    },
  },

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

    async clear(keepBookmarked = true) {
      const response = await apiClient.delete('/history', {
        params: { keep_bookmarked: keepBookmarked },
      })
      return response.data
    },

    async getStats() {
      const response = await apiClient.get('/history/stats/summary')
      return response.data
    },
  },

  // Anomaly detection
  evaluation: {
    async cases(databaseId: number): Promise<any[]> {
      return (await apiClient.get('/eval/cases', { params: { database_id: databaseId } })).data
    },
    async addCase(question: string, expectedSql: string, databaseId: number) {
      return (await apiClient.post('/eval/cases', { question, expected_sql: expectedSql, database_id: databaseId })).data
    },
    async importBookmarks(databaseId: number): Promise<{ added: number }> {
      return (await apiClient.post('/eval/cases/from-bookmarks', null, { params: { database_id: databaseId } })).data
    },
    async removeCase(id: number): Promise<void> {
      await apiClient.delete(`/eval/cases/${id}`)
    },
    async start(databaseId: number): Promise<any> {
      return (await apiClient.post('/eval/run', { database_id: databaseId })).data
    },
    async runs(): Promise<any[]> {
      return (await apiClient.get('/eval/runs')).data
    },
    async run(id: number): Promise<any> {
      return (await apiClient.get(`/eval/runs/${id}`)).data
    },
  },

  reports: {
    async list(): Promise<Report[]> {
      return (await apiClient.get('/reports')).data
    },
    async create(data: NewReport): Promise<Report> {
      return (await apiClient.post('/reports', data)).data
    },
    async get(id: number): Promise<Report & { results: any[] }> {
      return (await apiClient.get(`/reports/${id}`)).data
    },
    async run(id: number): Promise<Report & { results: any[] }> {
      return (await apiClient.post(`/reports/${id}/run`)).data
    },
    async setActive(id: number, active: boolean): Promise<Report> {
      return (await apiClient.patch(`/reports/${id}`, { is_active: active })).data
    },
    async remove(id: number): Promise<void> {
      await apiClient.delete(`/reports/${id}`)
    },
  },

  anomaly: {
    async getSettings() {
      return (await apiClient.get('/anomaly/settings')).data
    },

    async saveSettings(overrides: Record<string, Record<string, any>>) {
      return (await apiClient.put('/anomaly/settings', { overrides })).data
    },

    /** The holidays that apply in a year under the given (possibly unsaved) settings. */
    async holidayPreview(body: { year: number; auto_holidays: boolean; holidays: string[]; holiday_exceptions: string[] }) {
      return (await apiClient.post('/anomaly/holidays', body)).data
    },

    /** Is one date counted as a holiday under the given (possibly unsaved) settings, and why. */
    async holidayCheck(body: { date: string; auto_holidays: boolean; holidays: string[]; holiday_exceptions: string[] }) {
      return (await apiClient.post('/anomaly/holidays/check', body)).data
    },

    /** Where the holiday list comes from and how the last sync went. Never the key. */
    async holidayStatus() {
      return (await apiClient.get('/anomaly/holidays/status')).data
    },

    /** Fetch announced holidays now. */
    async holidaySync() {
      return (await apiClient.post('/anomaly/holidays/sync')).data
    },

    /** Save the 공공데이터포털 service key (admin); blank forgets it. */
    async holidayKey(key: string) {
      return (await apiClient.put('/anomaly/holidays/service-key', { key })).data
    },

    /** Merchant categories present in the data (name, count), most common first. */
    async categories(databaseId: string): Promise<{ name: string; count: number }[]> {
      const response = await apiClient.get('/anomaly/categories', { params: { database_id: databaseId } })
      return response.data.categories
    },

    /** Recent changes to the thresholds, newest first. */
    async settingsHistory(): Promise<AnomalySettingHistory[]> {
      return (await apiClient.get('/anomaly/settings/history')).data
    },

    /** Put the thresholds back as they were before that change. */
    async restoreSettings(entryId: number) {
      return (await apiClient.post(`/anomaly/settings/history/${entryId}/restore`)).data
    },

    async listSources(databaseId: string) {
      const response = await apiClient.get('/anomaly/sources', {
        params: { database_id: databaseId },
      })
      return response.data
    },

    async listFindings(params: {
      database_id: string
      template?: string
      status?: string
      source?: string
      date_from?: string
      date_to?: string
    }) {
      const response = await apiClient.get('/anomaly/findings', { params })
      return response.data
    },

    // Only called when a reviewer expands a row. The response carries the card
    // number, which is why it is a separate request rather than part of the list.
    async transactions(databaseId: string, source: string, seqs: number[]) {
      const params = new URLSearchParams({ database_id: databaseId, source })
      seqs.forEach((seq) => params.append('seq', String(seq)))
      const response = await apiClient.get(`/anomaly/findings/transactions?${params}`)
      return response.data
    },

    // finding_key goes in the body, not the path: a SPLIT_PAYMENT key contains a
    // full card number, which must not reach proxy logs or browser history.
    async review(data: {
      database_id: string
      finding_key: string
      status: 'confirmed' | 'dismissed'
      fingerprint: string
      note?: string
    }) {
      const response = await apiClient.patch('/anomaly/findings/review', data)
      return response.data
    },
  },
}

export default apiClient
