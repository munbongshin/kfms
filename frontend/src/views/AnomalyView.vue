<template>
  <div class="anomaly-view">
    <div class="page-title">
      <h2>이상거래 점검</h2>
      <button class="action" :disabled="store.loading || !store.findings.length" @click="exportCsv">
        파일저장
      </button>
    </div>

    <p class="notice">
      선택한 점검 대상과 기간에서 감사 기준 위반이 의심되는 거래를 찾습니다.
      판정한 건은 다음 조회부터 상태가 함께 표시됩니다.
    </p>

    <el-alert
      v-if="!databaseStore.activeConnectionId"
      type="info"
      :closable="false"
      show-icon
      title="좌측에서 데이터베이스 연결을 선택하세요"
    />

    <template v-else>
      <el-alert
        v-if="store.caveat"
        type="warning"
        :closable="false"
        show-icon
        :title="store.caveat"
        class="caveat"
      />

      <div class="search-box">
        <div class="fields">
          <label class="lbl">점검대상</label>
          <div class="ctl">
            <el-select v-model="store.sourceFilter" size="small" style="width: 190px">
              <el-option
                v-for="s in store.sources"
                :key="s.key"
                :label="`${s.label} (${s.row_count.toLocaleString()}건)`"
                :value="s.key"
              />
            </el-select>
          </div>

          <label class="lbl">규칙</label>
          <div class="ctl">
            <el-select
              v-model="store.ruleFilter"
              size="small"
              placeholder="전체"
              clearable
              style="width: 190px"
            >
              <el-option
                v-for="r in store.rules"
                :key="r.rule_code"
                :label="r.label"
                :value="r.rule_code"
              />
            </el-select>
          </div>

          <label class="lbl">조회기간</label>
          <div class="ctl period">
            <el-date-picker
              v-model="store.dateFrom"
              type="date"
              size="small"
              value-format="YYYY-MM-DD"
              placeholder="시작일"
              clearable
              style="width: 140px"
            />
            <span class="tilde">~</span>
            <el-date-picker
              v-model="store.dateTo"
              type="date"
              size="small"
              value-format="YYYY-MM-DD"
              placeholder="종료일"
              clearable
              style="width: 140px"
            />
            <span class="quick">
              <button v-for="q in QUICK" :key="q.label" @click="applyQuick(q.months)">
                {{ q.label }}
              </button>
            </span>
          </div>

          <label class="lbl">검토상태</label>
          <div class="ctl">
            <el-select
              v-model="store.statusFilter"
              size="small"
              placeholder="전체"
              clearable
              style="width: 190px"
            >
              <el-option label="미검토" value="unreviewed" />
              <el-option label="확인함" value="confirmed" />
              <el-option label="정상" value="dismissed" />
            </el-select>
          </div>
        </div>

        <button class="search" :disabled="store.loading" @click="refresh">
          <el-icon><Search /></el-icon>
          조회
        </button>
      </div>

      <div class="rules">
        <span
          v-for="rule in store.rules"
          :key="rule.rule_code"
          class="rule-chip"
          :class="{ off: !rule.applicable }"
        >
          {{ rule.label }}<em v-if="rule.caveat"> · {{ rule.caveat }}</em>
        </span>
      </div>

      <div class="result-head">
        조회결과 <strong>{{ store.findings.length }}</strong>건
      </div>

      <el-table
        :data="store.findings"
        v-loading="store.loading"
        size="small"
        border
        style="width: 100%"
        @expand-change="onExpand"
      >
        <el-table-column type="expand">
          <template #default="{ row }">
            <div v-loading="store.detailLoading[row.finding_key]" class="detail">
              <div
                v-for="tx in store.details[row.finding_key] || []"
                :key="tx.seq"
                class="detail-card"
              >
                <table class="detail-table">
                  <tbody>
                    <tr v-for="pair in pairUp(tx.core)" :key="pair[0].field">
                      <th>{{ pair[0].label }}</th>
                      <td>{{ display(pair[0].value) }}</td>
                      <th>{{ pair[1] ? pair[1].label : '' }}</th>
                      <td>{{ pair[1] ? display(pair[1].value) : '' }}</td>
                    </tr>
                  </tbody>
                </table>

                <button class="link" @click="toggleAll(tx.seq)">
                  {{ expandedAll.has(tx.seq) ? '전체 숨기기' : `전체 보기 (${tx.rest.length}개 항목)` }}
                </button>

                <table v-if="expandedAll.has(tx.seq)" class="detail-table rest">
                  <tbody>
                    <tr v-for="pair in pairUp(tx.rest)" :key="pair[0].field">
                      <th>{{ pair[0].label }}</th>
                      <td>{{ display(pair[0].value) }}</td>
                      <th>{{ pair[1] ? pair[1].label : '' }}</th>
                      <td>{{ pair[1] ? display(pair[1].value) : '' }}</td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </div>
          </template>
        </el-table-column>

        <el-table-column label="No." type="index" width="56" align="center" />

        <el-table-column label="심각도" width="80" align="center">
          <template #default="{ row }">
            <span class="sev" :class="row.severity">{{ severityLabel(row.severity) }}</span>
          </template>
        </el-table-column>

        <el-table-column prop="occurred_on" label="거래일" width="110" align="center" />

        <el-table-column label="점검사유" min-width="280">
          <template #default="{ row }">
            {{ row.summary }}
            <span v-if="row.stale" class="stale">검토 후 변경됨</span>
          </template>
        </el-table-column>

        <el-table-column label="금액" width="130" align="right">
          <template #default="{ row }">{{ row.amount.toLocaleString() }}</template>
        </el-table-column>

        <el-table-column label="건수" width="70" align="right">
          <template #default="{ row }">{{ row.transactions.length }}</template>
        </el-table-column>

        <el-table-column label="검토" width="150" align="center" fixed="right">
          <template #default="{ row }">
            <span v-if="!row.review || row.stale" class="review-actions">
              <button class="mini" @click="store.review(connectionId, row, 'confirmed')">확인</button>
              <button class="mini" @click="store.review(connectionId, row, 'dismissed')">정상</button>
            </span>
            <span v-else class="reviewed" :class="row.review.status">
              {{ row.review.status === 'dismissed' ? '정상' : '확인함' }}
            </span>
          </template>
        </el-table-column>

        <template #empty>
          <span class="empty">조회된 건이 없습니다. 기간이나 점검대상을 바꿔 다시 조회하세요.</span>
        </template>
      </el-table>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { Search } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { useAnomalyStore, type DetailField, type Finding } from '../stores/anomaly'
import { useDatabaseStore } from '../stores/database'

const store = useAnomalyStore()
const databaseStore = useDatabaseStore()

const connectionId = computed(() => String(databaseStore.activeConnectionId ?? ''))
const expandedAll = ref(new Set<number>())

// Anchored on the source's own latest date rather than today, so the same
// buttons work on historical data and on a live system where the two coincide.
const QUICK: Array<{ label: string; months: number | null }> = [
  { label: '전체', months: null },
  { label: '1개월', months: 1 },
  { label: '3개월', months: 3 },
  { label: '6개월', months: 6 },
]

const activeSource = computed(() => store.sources.find((s) => s.key === store.sourceFilter))

function applyQuick(months: number | null) {
  const source = activeSource.value
  if (!source || !source.min_date || !source.max_date) return

  store.dateTo = source.max_date

  if (months === null) {
    store.dateFrom = source.min_date
    return
  }

  const start = new Date(source.max_date)
  start.setMonth(start.getMonth() - months)
  const iso = start.toISOString().slice(0, 10)
  store.dateFrom = iso < source.min_date ? source.min_date : iso
}

function severityLabel(severity: string) {
  return severity === 'high' ? '높음' : severity === 'medium' ? '보통' : '낮음'
}

function display(value: string | number | null) {
  return value === null || value === '' ? '-' : String(value)
}

/** Two label/value columns per row, the way the reference screens lay out detail. */
function pairUp(fields: DetailField[]) {
  const pairs: DetailField[][] = []
  for (let i = 0; i < fields.length; i += 2) {
    pairs.push([fields[i], fields[i + 1]])
  }
  return pairs
}

function onExpand(row: Finding, expanded: Finding[]) {
  if (expanded.includes(row) && connectionId.value) {
    store.fetchDetail(connectionId.value, row)
  }
}

function toggleAll(seq: number) {
  const next = new Set(expandedAll.value)
  next.has(seq) ? next.delete(seq) : next.add(seq)
  expandedAll.value = next
}

function exportCsv() {
  const header = ['거래일', '심각도', '점검사유', '금액', '건수', '검토상태']
  const rows = store.findings.map((f) => [
    f.occurred_on,
    severityLabel(f.severity),
    f.summary,
    String(f.amount),
    String(f.transactions.length),
    f.review ? (f.review.status === 'dismissed' ? '정상' : '확인함') : '미검토',
  ])
  const csv = [header, ...rows]
    .map((r) => r.map((c) => `"${String(c).replace(/"/g, '""')}"`).join(','))
    .join('\n')

  // BOM so Excel reads the Korean text as UTF-8.
  const url = URL.createObjectURL(new Blob(['﻿' + csv], { type: 'text/csv' }))
  const a = document.createElement('a')
  a.href = url
  a.download = `이상거래점검_${store.dateFrom || '전체'}_${store.dateTo || '전체'}.csv`
  a.click()
  URL.revokeObjectURL(url)
  ElMessage.success(`${store.findings.length}건을 저장했습니다`)
}

function refresh() {
  if (connectionId.value) {
    store.fetchFindings(connectionId.value)
  } else {
    store.reset()
  }
}

async function reload() {
  if (!connectionId.value) {
    store.reset()
    return
  }
  // Sources first: the period is seeded from the source's own date range, so
  // findings must wait until that range is known.
  await store.fetchSources(connectionId.value)
  refresh()
}

watch(connectionId, () => {
  store.dateFrom = ''
  store.dateTo = ''
  reload()
})
onMounted(reload)
</script>

<style scoped>
.anomaly-view {
  font-size: 12px;
  color: #333;
}

.page-title {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding-bottom: 8px;
  border-bottom: 2px solid #1b3c74;
}

.page-title h2 {
  display: flex;
  align-items: center;
  gap: 7px;
  margin: 0;
  font-size: 15px;
  font-weight: 700;
  color: #1b3c74;
}

.page-title h2::before {
  content: '';
  width: 3px;
  height: 14px;
  background: #1a5fa8;
}

.action {
  padding: 4px 12px;
  border: 1px solid #b9c3d1;
  background: #fff;
  color: #1b3c74;
  font-size: 12px;
  cursor: pointer;
}

.action:hover:not(:disabled) {
  border-color: #1a5fa8;
  color: #1a5fa8;
}

.action:disabled {
  color: #b0b6bf;
  cursor: not-allowed;
}

.notice {
  position: relative;
  margin: 8px 0 10px;
  padding-left: 11px;
  color: #5a6472;
  line-height: 1.6;
}

.notice::before {
  content: '';
  position: absolute;
  left: 0;
  top: 7px;
  width: 3px;
  height: 3px;
  background: #1a5fa8;
}

.caveat {
  margin-bottom: 10px;
}

.search-box {
  display: flex;
  gap: 12px;
  padding: 12px 14px;
  background: #f7f9fc;
  border: 1px solid #d3dae3;
}

.fields {
  flex: 1;
  display: grid;
  grid-template-columns: max-content minmax(0, 1fr) max-content minmax(0, 1fr);
  align-items: center;
  gap: 8px 10px;
}

.lbl {
  color: #1a5fa8;
  font-weight: 600;
  white-space: nowrap;
}

.ctl {
  display: flex;
  align-items: center;
  gap: 6px;
  min-width: 0;
}

.period {
  grid-column: 2 / -1;
  flex-wrap: wrap;
}

.tilde {
  color: #8a94a3;
}

.quick {
  display: inline-flex;
  margin-left: 4px;
}

.quick button {
  margin-left: -1px;
  padding: 4px 9px;
  border: 1px solid #c4ccd8;
  background: #fff;
  color: #4a5567;
  font-size: 11px;
  cursor: pointer;
}

.quick button:hover {
  border-color: #1a5fa8;
  background: #eaf1fa;
  color: #1a5fa8;
}

.search {
  display: flex;
  align-self: center;
  align-items: center;
  justify-content: center;
  gap: 5px;
  min-width: 78px;
  padding: 8px 14px;
  border: 1px solid #1a5fa8;
  background: #fff;
  color: #1a5fa8;
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
}

.search:hover:not(:disabled) {
  background: #1a5fa8;
  color: #fff;
}

.search:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.rules {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin: 10px 0;
}

.rule-chip {
  padding: 3px 8px;
  border: 1px solid #c8d6e8;
  background: #f2f6fc;
  color: #1b3c74;
}

.rule-chip em {
  font-style: normal;
  color: #7b8494;
}

.rule-chip.off {
  border-color: #dcdfe4;
  background: #f5f5f6;
  color: #9aa1ab;
}

.result-head {
  padding: 6px 0;
  color: #4a5567;
}

.result-head strong {
  color: #1a5fa8;
}

.sev {
  display: inline-block;
  min-width: 34px;
  padding: 1px 5px;
  border: 1px solid;
  font-size: 11px;
}

.sev.high {
  border-color: #d98d8d;
  background: #fdf3f3;
  color: #b53d3d;
}

.sev.medium {
  border-color: #dcc08a;
  background: #fdf9f0;
  color: #9a6f1f;
}

.sev.low {
  border-color: #c4ccd8;
  background: #f7f9fc;
  color: #5a6472;
}

.stale {
  margin-left: 6px;
  padding: 1px 5px;
  border: 1px solid #dcc08a;
  background: #fdf9f0;
  color: #9a6f1f;
  font-size: 11px;
}

.review-actions {
  display: inline-flex;
  gap: 4px;
}

.mini {
  padding: 3px 9px;
  border: 1px solid #b9c3d1;
  background: #fff;
  color: #3b4655;
  font-size: 11px;
  cursor: pointer;
}

.mini:hover {
  border-color: #1a5fa8;
  color: #1a5fa8;
}

.reviewed {
  color: #5a6472;
}

.reviewed.confirmed {
  color: #1a7a43;
  font-weight: 600;
}

.empty {
  color: #8a94a3;
}

.detail {
  min-height: 36px;
  padding: 10px 14px;
  background: #fbfcfe;
}

.detail-card + .detail-card {
  margin-top: 10px;
  padding-top: 10px;
  border-top: 1px dashed #d3dae3;
}

.detail-table {
  width: 100%;
  border-collapse: collapse;
  table-layout: fixed;
}

.detail-table th,
.detail-table td {
  padding: 5px 8px;
  border: 1px solid #e2e7ee;
  font-weight: normal;
  text-align: left;
  word-break: break-all;
}

.detail-table th {
  width: 14%;
  background: #f2f5f9;
  color: #4a5567;
  white-space: nowrap;
}

.detail-table.rest {
  margin-top: 8px;
}

.link {
  margin-top: 8px;
  padding: 0;
  border: none;
  background: none;
  color: #1a5fa8;
  font-size: 12px;
  text-decoration: underline;
  cursor: pointer;
}

:deep(.el-table th.el-table__cell) {
  padding: 7px 0;
  background: #edf1f7;
  color: #33415c;
  font-weight: 600;
}

:deep(.el-table td.el-table__cell) {
  padding: 5px 0;
}

:deep(.el-table) {
  --el-table-border-color: #d3dae3;
  font-size: 12px;
}
</style>
