/**
 * Query Store (Pinia)
 * Manages query execution state
 */
import { defineStore } from 'pinia'
import { ref } from 'vue'
import { api } from '../services/api'
import { ElMessage } from 'element-plus'

export interface QueryResult {
  question: string
  sql: string
  results: any[]
  row_count: number
  execution_time_ms: number
  history_id: number
  warnings?: string[]
}

export interface TablePreview {
  table: string
  columns: string[]
  selected: string[]
  orderBy: string | null
  descending: boolean
  total: number
  page: number
  pageSize: number
}

export const useQueryStore = defineStore('query', () => {
  // State
  const currentQuestion = ref('')
  const generatedSQL = ref('')
  const validationResult = ref<any>(null)
  const queryResults = ref<QueryResult | null>(null)
  const loading = ref(false)
  const showSQLPreview = ref(false)
  const showValidationDialog = ref(false)

  // Temporary storage for execution
  const pendingExecution = ref<any>(null)

  // Set only while a table preview is on screen; paging and column choice
  // live here rather than in the generic result, which an LLM query fills.
  const preview = ref<TablePreview | null>(null)

  // Actions
  async function generateSQL(question: string, databaseId: number, llmProvider?: string) {
    loading.value = true
    currentQuestion.value = question

    try {
      const result = await api.query.generate({
        question,
        database_id: databaseId,
        llm_provider: llmProvider,
      })

      generatedSQL.value = result.sql
      validationResult.value = result.validation

      // Store for later execution
      pendingExecution.value = {
        question,
        sql: result.sql,
        database_id: databaseId,
        llm_provider: result.llm_provider,
        llm_model: result.llm_model,
      }

      // Show SQL preview
      showSQLPreview.value = true

      // Check if safe
      if (!result.validation.is_safe) {
        ElMessage.warning({
          message: 'SQL validation warnings detected. Please review before executing.',
          duration: 5000
        })
      } else if (result.validation.warnings && result.validation.warnings.length > 0) {
        ElMessage.info({
          message: `Generated SQL with ${result.validation.warnings.length} warning(s)`,
          duration: 3000
        })
      } else {
        ElMessage.success('SQL generated successfully')
      }

      return result
    } catch (error: any) {
      const message = error.response?.data?.detail || 'Failed to generate SQL'
      ElMessage.error(message)
      throw error
    } finally {
      loading.value = false
    }
  }

  async function executeSQL() {
    if (!pendingExecution.value) {
      ElMessage.error('No query to execute')
      return
    }

    loading.value = true

    try {
      const result = await api.query.execute({
        ...pendingExecution.value,
        validation_approved: true,
      })

      if (result.success) {
        queryResults.value = {
          question: pendingExecution.value.question,
          sql: pendingExecution.value.sql,
          results: result.results || [],
          row_count: result.row_count || 0,
          execution_time_ms: result.execution_time_ms || 0,
          history_id: result.history_id,
          warnings: result.warnings,
        }

        showSQLPreview.value = false

        ElMessage.success({
          message: `Query executed successfully. ${result.row_count} rows returned in ${result.execution_time_ms}ms`,
          duration: 3000
        })

        return result
      } else {
        throw new Error(result.error || 'Execution failed')
      }
    } catch (error: any) {
      const message = error.response?.data?.detail || error.message || 'Failed to execute query'
      ElMessage.error(message)
      throw error
    } finally {
      loading.value = false
    }
  }

  async function directExecute(question: string, databaseId: number, llmProvider?: string) {
    loading.value = true
    currentQuestion.value = question

    try {
      const result = await api.query.generateAndExecute({
        question,
        database_id: databaseId,
        llm_provider: llmProvider,
        auto_approve: false,
      })

      if (result.requires_approval) {
        // Show SQL for approval
        generatedSQL.value = result.generation.sql
        validationResult.value = result.generation.validation
        pendingExecution.value = {
          question,
          sql: result.generation.sql,
          database_id: databaseId,
          llm_provider: result.generation.llm_provider,
          llm_model: result.generation.llm_model,
        }
        showSQLPreview.value = true

        ElMessage.warning('Please review and confirm SQL execution')
        return
      }

      if (result.success) {
        queryResults.value = {
          question,
          sql: result.generation.sql,
          results: result.results || [],
          row_count: result.row_count || 0,
          execution_time_ms: result.execution_time_ms || 0,
          history_id: result.history_id,
          warnings: result.warnings,
        }

        ElMessage.success(`Query executed in ${result.execution_time_ms}ms`)
        return result
      }
    } catch (error: any) {
      const message = error.response?.data?.detail || 'Query failed'
      ElMessage.error(message)
      throw error
    } finally {
      loading.value = false
    }
  }

  function cancelExecution() {
    showSQLPreview.value = false
    pendingExecution.value = null
  }

  function insertIdentifier(name: string) {
    const current = currentQuestion.value
    if (!current) {
      currentQuestion.value = name
    } else if (current.endsWith(' ')) {
      currentQuestion.value = `${current}${name}`
    } else {
      currentQuestion.value = `${current} ${name}`
    }
  }

  async function previewTable(tableName: string, databaseId: number, page = 1) {
    loading.value = true

    // A new table starts from its own defaults; paging the current one keeps
    // the reviewer's column choice and sort.
    if (preview.value?.table !== tableName) {
      preview.value = {
        table: tableName,
        columns: [],
        selected: [],
        orderBy: null,
        descending: false,
        total: 0,
        page: 1,
        pageSize: preview.value?.pageSize ?? 100,
      }
      page = 1
    }

    const state = preview.value!

    try {
      const data = await api.databases.readTable(databaseId, tableName, {
        columns: state.selected.length ? state.selected.join(',') : undefined,
        order_by: state.orderBy ?? undefined,
        descending: state.descending,
        limit: state.pageSize,
        offset: (page - 1) * state.pageSize,
      })

      state.columns = data.columns
      state.orderBy = data.order_by
      state.total = data.total
      state.page = page

      queryResults.value = {
        question: `[미리보기] ${tableName}`,
        sql: '',
        results: data.rows,
        row_count: data.total,
        execution_time_ms: 0,
        history_id: 0,
      }
    } catch (error: any) {
      const message = error.response?.data?.detail || error.message || '테이블을 읽지 못했습니다'
      ElMessage.error(message)
      throw error
    } finally {
      loading.value = false
    }
  }

  async function runSavedSQL(question: string, sql: string, databaseId: number) {
    loading.value = true
    currentQuestion.value = question
    generatedSQL.value = sql

    try {
      const result = await api.query.execute({
        question,
        sql,
        database_id: databaseId,
        validation_approved: true,
      })

      if (!result.success) {
        throw new Error(result.error || 'Execution failed')
      }

      queryResults.value = {
        question,
        sql,
        results: result.results || [],
        row_count: result.row_count || 0,
        execution_time_ms: result.execution_time_ms || 0,
        history_id: result.history_id,
        warnings: result.warnings,
      }

      ElMessage.success(`저장된 SQL 실행 완료 (${result.execution_time_ms}ms)`)
      return result
    } catch (error: any) {
      // Saved SQL goes stale when the schema changes, so fall back to
      // regenerating rather than leaving the user at a dead end.
      ElMessage.warning('저장된 SQL이 현재 스키마에서 실패해 다시 생성합니다')
      return await directExecute(question, databaseId)
    } finally {
      loading.value = false
    }
  }

  function clearResults() {
    preview.value = null
    queryResults.value = null
    currentQuestion.value = ''
    generatedSQL.value = ''
    validationResult.value = null
    pendingExecution.value = null
  }

  return {
    // State
    currentQuestion,
    generatedSQL,
    validationResult,
    queryResults,
    loading,
    showSQLPreview,
    showValidationDialog,
    pendingExecution,
    preview,

    // Actions
    generateSQL,
    executeSQL,
    directExecute,
    cancelExecution,
    clearResults,
    insertIdentifier,
    previewTable,
    runSavedSQL,
  }
})
