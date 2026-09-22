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

export const useAnomalyStore = defineStore('anomaly', () => {
  const rules = ref<RuleStatus[]>([])
  const findings = ref<Finding[]>([])
  const caveat = ref<string | null>(null)
  const loading = ref(false)
  const ruleFilter = ref('')
  const statusFilter = ref('')

  function reset() {
    rules.value = []
    findings.value = []
    caveat.value = null
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

  return { rules, findings, caveat, loading, ruleFilter, statusFilter, reset, fetchFindings, review }
})
