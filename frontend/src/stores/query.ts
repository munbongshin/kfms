/**
 * Query Store (Pinia)
 * Manages query execution state
 */
import { t } from '../i18n'
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
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
  // How the SQL was reached: retries after a database error, and what guided it.
  const generationInfo = ref<{ attempts: number; examples_used: number; terms_used: string[] } | null>(null)
  const showValidationDialog = ref(false)

  // Temporary storage for execution
  const pendingExecution = ref<any>(null)

  // Set only while a table preview is on screen; paging and column choice
  // live here rather than in the generic result, which an LLM query fills.
  const preview = ref<TablePreview | null>(null)

  // Whether the next question continues the one on screen ("그중 상위 5개만").
  const followUp = ref(true)

  /** The question and SQL now on screen, when the next question may follow them.
   *  A table preview is not a question, so there is nothing to follow. */
  const canFollowUp = computed(
    () =>
      !preview.value &&
      !!queryResults.value?.question &&
      // People who cannot see SQL have only the history record to point at.
      (!!queryResults.value?.history_id || !!queryResults.value?.sql)
  )

  function previousTurn() {
    if (!followUp.value || !canFollowUp.value) return {}
    const shown = queryResults.value!
    if (shown.history_id) return { previous_history_id: shown.history_id }
    return { previous_question: shown.question, previous_sql: shown.sql }
  }

  // Actions
  async function generateSQL(question: string, databaseId: number, llmProvider?: string) {
    loading.value = true
    currentQuestion.value = question

    try {
      const result = await api.query.generate({
        question,
        database_id: databaseId,
        llm_provider: llmProvider,
        ...previousTurn(),
      })

      generatedSQL.value = result.sql
      validationResult.value = result.validation
      generationInfo.value = {
        attempts: result.attempts ?? 1,
        examples_used: result.examples_used ?? 0,
        terms_used: result.terms_used ?? [],
      }

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
          message: t('SQL 검증 경고가 있습니다. 실행하기 전에 확인하세요.'),
          duration: 5000
        })
      } else if (result.validation.warnings && result.validation.warnings.length > 0) {
        ElMessage.info({
          message: t('SQL을 생성했습니다 (경고 {n}건)', { n: result.validation.warnings.length }),
          duration: 3000
        })
      } else {
        ElMessage.success(t('SQL을 생성했습니다'))
      }

      return result
    } catch (error: any) {
      const message = error.response?.data?.detail || t('SQL을 생성하지 못했습니다')
      ElMessage.error(message)
      throw error
    } finally {
      loading.value = false
    }
  }

  async function executeSQL() {
    if (!pendingExecution.value) {
      ElMessage.error(t('실행할 쿼리가 없습니다'))
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
          message: t('쿼리를 실행했습니다 ({rows}행, {ms}ms)', { rows: Number(result.row_count).toLocaleString(), ms: result.execution_time_ms }),
          duration: 3000
        })

        return result
      } else {
        throw new Error(result.error || t('실행하지 못했습니다'))
      }
    } catch (error: any) {
      const message = error.response?.data?.detail || error.message || t('쿼리를 실행하지 못했습니다')
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
        ...previousTurn(),
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

        ElMessage.warning(t('SQL을 확인하고 실행할지 결정하세요'))
        return
      }

      if (result.success) {
        queryResults.value = {
          question,
          // Absent for anyone but an administrator: the server does not send it.
          sql: result.generation?.sql ?? '',
          results: result.results || [],
          row_count: result.row_count || 0,
          execution_time_ms: result.execution_time_ms || 0,
          history_id: result.history_id,
          warnings: result.warnings,
        }

        ElMessage.success(t('쿼리를 실행했습니다 ({ms}ms)', { ms: result.execution_time_ms }))
        return result
      }

      if (result.error) ElMessage.error(result.error)
    } catch (error: any) {
      const message = error.response?.data?.detail || t('질의에 실패했습니다')
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
        question: t('[미리보기] {table}', { table: tableName }),
        sql: data.sql ?? '',
        results: data.rows,
        row_count: data.total,
        execution_time_ms: 0,
        history_id: 0,
      }
    } catch (error: any) {
      const message = error.response?.data?.detail || error.message || t('테이블을 읽지 못했습니다')
      ElMessage.error(message)
      throw error
    } finally {
      loading.value = false
    }
  }

  /** Run a saved question again. With a history id the server looks the SQL up
   *  (the only way for someone who cannot see it); `sql` is then just for display. */
  async function runSavedSQL(question: string, sql: string, databaseId: number, historyId?: number) {
    loading.value = true
    currentQuestion.value = question
    generatedSQL.value = sql

    try {
      const result = historyId
        ? await api.query.rerun(historyId)
        : await api.query.execute({
            question,
            sql,
            database_id: databaseId,
            validation_approved: true,
          })

      if (!result.success) {
        throw new Error(result.error || t('실행하지 못했습니다'))
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

      ElMessage.success(t('저장된 질문 실행 완료 ({ms}ms)', { ms: result.execution_time_ms }))
      return result
    } catch (error: any) {
      // Saved SQL goes stale when the schema changes, so fall back to
      // regenerating rather than leaving the user at a dead end.
      ElMessage.warning(t('저장된 질문이 현재 스키마에서 실패해 다시 만듭니다'))
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
    generationInfo,
    followUp,
    canFollowUp,
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
