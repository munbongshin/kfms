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

  function clearResults() {
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

    // Actions
    generateSQL,
    executeSQL,
    directExecute,
    cancelExecution,
    clearResults,
  }
})
