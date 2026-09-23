/**
 * Anomaly Store (Pinia)
 * Findings for the active connection plus reviewer actions.
 */
import { defineStore } from 'pinia'
import { ref } from 'vue'
import { ElMessage } from 'element-plus'
import { api } from '../services/api'

export interface RuleStatus {
  rule_code: string
  label: string
  applicable: boolean
  caveat?: string
}

export interface FindingReview {
  status: 'confirmed' | 'dismissed'
  note: string | null
  reviewed_at: string
}

export interface Finding {
  finding_key: string
  rule_code: string
  severity: 'high' | 'medium' | 'low'
  summary: string
  amount: number
  occurred_on: string
  transactions: any[]
  fingerprint: string
  review: FindingReview | null
  stale: boolean
}

export interface AnomalySource {
  key: string
  label: string
  min_date: string | null
  max_date: string | null
  row_count: number
}

export interface DetailField {
  field: string
  label: string
  value: string | number | null
}

export interface TransactionDetail {
  seq: number
  core: DetailField[]
  rest: DetailField[]
}

export const useAnomalyStore = defineStore('anomaly', () => {
  const rules = ref<RuleStatus[]>([])
  const findings = ref<Finding[]>([])
  const caveat = ref<string | null>(null)
  const loading = ref(false)
  const ruleFilter = ref('')
  const statusFilter = ref('')
  const sources = ref<AnomalySource[]>([])
  const sourceFilter = ref('')
  // Two independent bounds, not one range: a daterange picker restarts the whole
  // selection on every click, so a reviewer could not adjust just the end date.
  // Either may be empty — the backend treats a missing bound as open-ended.
  const dateFrom = ref<string>('')
  const dateTo = ref<string>('')

  // Keyed by finding_key. Card numbers live here, so it is dropped with the
  // rest of the state whenever the connection changes or a fetch fails.
  const details = ref<Record<string, TransactionDetail[]>>({})
  const detailLoading = ref<Record<string, boolean>>({})

  function reset() {
    rules.value = []
    findings.value = []
    caveat.value = null
    details.value = {}
    detailLoading.value = {}
  }

  async function fetchDetail(databaseId: string, finding: Finding) {
    if (details.value[finding.finding_key] || detailLoading.value[finding.finding_key]) return

    detailLoading.value[finding.finding_key] = true
    try {
      const seqs = finding.transactions.map((t) => Number(t.seq))
      const data = await api.anomaly.transactions(databaseId, seqs)
      details.value[finding.finding_key] = data.transactions
    } catch (error) {
      ElMessage.error('거래 상세를 불러오지 못했습니다')
    } finally {
      delete detailLoading.value[finding.finding_key]
    }
  }

  async function fetchSources(databaseId: string) {
    try {
      const data = await api.anomaly.listSources(databaseId)
      sources.value = data.sources
      const active = sources.value.find((s) => s.key === sourceFilter.value) ?? sources.value[0]
      if (active) {
        sourceFilter.value = active.key
        if (!dateFrom.value && !dateTo.value && active.min_date && active.max_date) {
          dateFrom.value = active.min_date
          dateTo.value = active.max_date
        }
      }
    } catch (error) {
      sources.value = []
      ElMessage.error('점검 가능한 원천을 불러오지 못했습니다')
    }
  }

  async function fetchFindings(databaseId: string) {
    // Clear first: otherwise the previous connection's rows stay visible under
    // the loading overlay, and stay on screen if the fetch then fails.
    reset()
    loading.value = true
    try {
      const data = await api.anomaly.listFindings({
        database_id: databaseId,
        rule_code: ruleFilter.value || undefined,
        status: statusFilter.value || undefined,
        source: sourceFilter.value || undefined,
        date_from: dateFrom.value || undefined,
        date_to: dateTo.value || undefined,
      })
      rules.value = data.applicable_rules
      findings.value = data.findings
      caveat.value = data.caveat ?? null
    } catch (error) {
      reset()
      ElMessage.error('점검 결과를 불러오지 못했습니다')
    } finally {
      loading.value = false
    }
  }

  async function review(
    databaseId: string,
    finding: Finding,
    status: 'confirmed' | 'dismissed'
  ) {
    try {
      const updated = await api.anomaly.review({
        database_id: databaseId,
        finding_key: finding.finding_key,
        status,
        // The fingerprint the reviewer actually saw, so a later change reopens it.
        fingerprint: finding.fingerprint,
      })
      finding.review = {
        status: updated.status,
        note: updated.note,
        reviewed_at: updated.reviewed_at,
      }
      finding.stale = false
      ElMessage.success(status === 'confirmed' ? '확인 처리했습니다' : '정상으로 표시했습니다')
    } catch (error) {
      ElMessage.error('검토 상태를 저장하지 못했습니다')
    }
  }

  return {
    rules,
    findings,
    caveat,
    loading,
    ruleFilter,
    statusFilter,
    sources,
    sourceFilter,
    dateFrom,
    dateTo,
    details,
    detailLoading,
    reset,
    fetchSources,
    fetchFindings,
    fetchDetail,
    review,
  }
})
