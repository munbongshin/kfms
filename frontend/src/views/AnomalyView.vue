<template>
  <div class="anomaly-view">
    <el-card>
      <template #header>
        <div class="header">
          <span>이상거래 점검</span>
          <el-button :loading="store.loading" @click="refresh">
            <el-icon><Refresh /></el-icon>
            다시 검사
          </el-button>
        </div>
      </template>

      <el-alert
        v-if="!databaseStore.activeConnectionId"
        type="info"
        :closable="false"
        show-icon
        title="먼저 좌측에서 데이터베이스 연결을 선택하세요"
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

        <div class="rules">
          <el-tag
            v-for="rule in store.rules"
            :key="rule.rule_code"
            :type="rule.applicable ? 'success' : 'info'"
            :effect="rule.applicable ? 'light' : 'plain'"
            class="rule-tag"
          >
            {{ rule.label }}<span v-if="rule.caveat"> — {{ rule.caveat }}</span>
          </el-tag>
        </div>

        <div class="filters">
          <el-select
            v-model="store.sourceFilter"
            placeholder="점검 대상"
            style="width: 180px"
            :disabled="store.sources.length <= 1"
          >
            <el-option
              v-for="s in store.sources"
              :key="s.key"
              :label="`${s.label} (${s.row_count.toLocaleString()}건)`"
              :value="s.key"
            />
          </el-select>

          <el-date-picker
            v-model="store.period"
            type="daterange"
            value-format="YYYY-MM-DD"
            range-separator="~"
            start-placeholder="시작일"
            end-placeholder="종료일"
            style="width: 260px"
          />

          <el-select v-model="store.ruleFilter" placeholder="전체 규칙" clearable style="width: 180px">
            <el-option v-for="r in store.rules" :key="r.rule_code" :label="r.label" :value="r.rule_code" />
          </el-select>
          <el-select v-model="store.statusFilter" placeholder="전체 상태" clearable style="width: 160px">
            <el-option label="미검토" value="unreviewed" />
            <el-option label="확인함" value="confirmed" />
            <el-option label="정상" value="dismissed" />
          </el-select>
          <el-button @click="refresh">적용</el-button>
        </div>

        <el-table
          :data="store.findings"
          v-loading="store.loading"
          stripe
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
                  <div class="detail-grid">
                    <template v-for="f in tx.core" :key="f.field">
                      <span class="detail-label">{{ f.label }}</span>
                      <span class="detail-value">{{ display(f.value) }}</span>
                    </template>
                  </div>

                  <el-button text size="small" @click="toggleAll(tx.seq)">
                    {{ expandedAll.has(tx.seq) ? '전체 숨기기' : `전체 보기 (${tx.rest.length}개)` }}
                  </el-button>

                  <div v-if="expandedAll.has(tx.seq)" class="detail-grid rest">
                    <template v-for="f in tx.rest" :key="f.field">
                      <span class="detail-label">{{ f.label }}</span>
                      <span class="detail-value">{{ display(f.value) }}</span>
                    </template>
                  </div>
                </div>
              </div>
            </template>
          </el-table-column>

          <el-table-column label="심각도" width="90">
            <template #default="{ row }">
              <el-tag :type="severityType(row.severity)" size="small">{{ row.severity }}</el-tag>
            </template>
          </el-table-column>

          <el-table-column prop="occurred_on" label="거래일" width="120" />

          <el-table-column label="사유" min-width="280">
            <template #default="{ row }">
              {{ row.summary }}
              <el-tag v-if="row.stale" type="warning" size="small" class="stale">검토 후 변경됨</el-tag>
            </template>
          </el-table-column>

          <el-table-column label="금액" width="140" align="right">
            <template #default="{ row }">{{ row.amount.toLocaleString() }}</template>
          </el-table-column>

          <el-table-column label="건수" width="80" align="right">
            <template #default="{ row }">{{ row.transactions.length }}</template>
          </el-table-column>

          <el-table-column label="검토" width="200" fixed="right">
            <template #default="{ row }">
              <el-button-group v-if="!row.review || row.stale">
                <el-button size="small" @click="store.review(connectionId, row, 'confirmed')">확인</el-button>
                <el-button size="small" @click="store.review(connectionId, row, 'dismissed')">정상</el-button>
              </el-button-group>
              <el-tag v-else :type="row.review.status === 'dismissed' ? 'info' : 'success'" size="small">
                {{ row.review.status === 'dismissed' ? '정상' : '확인함' }}
              </el-tag>
            </template>
          </el-table-column>
        </el-table>

        <el-empty v-if="!store.loading && store.findings.length === 0" description="탐지된 건이 없습니다" />
      </template>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { Refresh } from '@element-plus/icons-vue'
import { useAnomalyStore, type Finding } from '../stores/anomaly'
import { useDatabaseStore } from '../stores/database'

const store = useAnomalyStore()
const databaseStore = useDatabaseStore()

const connectionId = computed(() => String(databaseStore.activeConnectionId ?? ''))
const expandedAll = ref(new Set<number>())

function severityType(severity: string) {
  return severity === 'high' ? 'danger' : severity === 'medium' ? 'warning' : 'info'
}

function display(value: string | number | null) {
  return value === null || value === '' ? '—' : String(value)
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

function refresh() {
  if (connectionId.value) {
    store.fetchFindings(connectionId.value)
  } else {
    // No connection selected: don't leave the previous one's rows on screen.
    store.reset()
  }
}

async function reload() {
  if (!connectionId.value) {
    store.reset()
    return
  }
  // Sources first: the period picker is seeded from the source's own date range,
  // so findings must wait until that range is known.
  await store.fetchSources(connectionId.value)
  refresh()
}

watch(connectionId, () => {
  // A different connection has a different date range; drop the old one.
  store.period = null
  reload()
})
onMounted(reload)
</script>

<style scoped>
.header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.detail {
  padding: 8px 16px;
  min-height: 40px;
}

.detail-card {
  padding: 12px 0;
  border-bottom: 1px solid #ebeef5;
}

.detail-card:last-child {
  border-bottom: none;
}

.detail-grid {
  display: grid;
  grid-template-columns: max-content minmax(0, 1fr) max-content minmax(0, 1fr);
  gap: 6px 14px;
  margin-bottom: 8px;
}

.detail-grid.rest {
  margin-top: 8px;
  padding-top: 8px;
  border-top: 1px dashed #ebeef5;
}

.detail-label {
  color: #909399;
  font-size: 12px;
  white-space: nowrap;
}

.detail-value {
  font-size: 13px;
  word-break: break-all;
}

.caveat {
  margin-bottom: 16px;
}

.rules {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 16px;
}

.filters {
  display: flex;
  gap: 10px;
  margin-bottom: 16px;
}

.stale {
  margin-left: 8px;
}
</style>
