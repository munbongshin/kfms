<template>
  <div class="reports-view">
    <div class="page-title">
      <h2>보고서</h2>
      <span class="sub">저장한 질문이 정한 시각에 자동 실행되고, 최근 결과가 여기에 남습니다.</span>
    </div>

    <el-table :data="reports" size="small" border v-loading="loading" empty-text="저장된 보고서가 없습니다. 질의 결과 위의 '보고서로 저장'으로 만드세요.">
      <el-table-column prop="name" label="이름" min-width="180" show-overflow-tooltip />
      <el-table-column label="주기" width="150">
        <template #default="{ row }">{{ schedule(row) }}</template>
      </el-table-column>
      <el-table-column label="마지막 실행" width="220">
        <template #default="{ row }">
          <template v-if="row.last_run_at">
            <el-tag :type="row.last_status === 'ok' ? 'success' : 'danger'" size="small">
              {{ row.last_status === 'ok' ? `${(row.last_row_count ?? 0).toLocaleString()}행` : '오류' }}
            </el-tag>
            <span class="time">{{ fmt(row.last_run_at) }}</span>
          </template>
          <span v-else class="muted">아직 실행 전</span>
        </template>
      </el-table-column>
      <el-table-column label="다음 실행" width="170">
        <template #default="{ row }">
          <span v-if="row.is_active">{{ fmt(row.next_run_at) }}</span>
          <el-tag v-else size="small" type="info">일시중지</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="created_by" label="만든 사람" width="110" />
      <el-table-column label="" width="260" align="center">
        <template #default="{ row }">
          <button class="link" @click="open(row)">결과</button>
          <button class="link" :disabled="running === row.id" @click="runNow(row)">
            {{ running === row.id ? '실행 중…' : '지금 실행' }}
          </button>
          <button class="link" @click="toggle(row)">{{ row.is_active ? '중지' : '재개' }}</button>
          <el-popconfirm title="이 보고서를 삭제할까요?" @confirm="remove(row)">
            <template #reference><button class="link danger">삭제</button></template>
          </el-popconfirm>
        </template>
      </el-table-column>
    </el-table>

    <el-dialog v-model="showResult" :title="current?.name" width="900px">
      <div v-if="current" class="detail">
        <div class="sqlbox">{{ current.sql }}</div>
        <el-alert v-if="current.last_status === 'error'" type="error" :closable="false" show-icon :title="current.last_error || '오류'" />
        <p v-else-if="current.last_run_at" class="note">
          {{ fmt(current.last_run_at) }} 실행 · 전체 {{ (current.last_row_count ?? 0).toLocaleString() }}행 중 앞 {{ results.length }}행을 보관합니다.
        </p>
        <p v-else class="note">아직 실행되지 않았습니다. '지금 실행'을 눌러 보세요.</p>
        <el-table v-if="results.length" :data="results" size="small" border max-height="420">
          <el-table-column v-for="c in columns" :key="c" :prop="c" :label="c" min-width="120" show-overflow-tooltip />
        </el-table>
      </div>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { api, type Report } from '../services/api'
import { describeSchedule } from '../utils/schedule'

const reports = ref<Report[]>([])
const loading = ref(false)
const running = ref<number | null>(null)
const showResult = ref(false)
const current = ref<(Report & { results?: any[] }) | null>(null)

const results = computed(() => current.value?.results || [])
const columns = computed(() => (results.value.length ? Object.keys(results.value[0]) : []))

const fmt = (iso: string | null) => (iso ? new Date(iso).toLocaleString() : '—')

const schedule = (r: Report) => describeSchedule(r.frequency, r.hour, r.weekday, r.day)

async function load() {
  loading.value = true
  try {
    reports.value = await api.reports.list()
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || '보고서를 불러오지 못했습니다')
  } finally {
    loading.value = false
  }
}

async function open(r: Report) {
  try {
    current.value = await api.reports.get(r.id)
    showResult.value = true
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || '결과를 불러오지 못했습니다')
  }
}

async function runNow(r: Report) {
  running.value = r.id
  try {
    current.value = await api.reports.run(r.id)
    await load()
    showResult.value = true
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || '실행하지 못했습니다')
  } finally {
    running.value = null
  }
}

async function toggle(r: Report) {
  try {
    await api.reports.setActive(r.id, !r.is_active)
    await load()
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || '변경하지 못했습니다')
  }
}

async function remove(r: Report) {
  try {
    await api.reports.remove(r.id)
    await load()
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || '삭제하지 못했습니다')
  }
}

onMounted(load)
</script>

<style scoped>
.reports-view {
  max-width: 1200px;
}

.page-title {
  display: flex;
  align-items: baseline;
  gap: 14px;
  margin-bottom: 10px;
}

.page-title h2 {
  margin: 0;
  padding-left: 10px;
  border-left: 4px solid #1b3c74;
  font-size: 18px;
  color: #1b3c74;
}

.sub {
  font-size: 13px;
  color: #6b7686;
}

.time {
  margin-left: 6px;
  font-size: 12px;
  color: #6b7686;
}

.muted {
  color: #98a2b3;
}

.link {
  padding: 0 6px;
  border: none;
  background: none;
  color: #1a5fa8;
  font-size: 12.5px;
  text-decoration: underline;
  cursor: pointer;
}

.link.danger {
  color: #b42318;
}

.link:disabled {
  color: #98a2b3;
  cursor: not-allowed;
}

.sqlbox {
  margin-bottom: 10px;
  padding: 8px 10px;
  background: #f7f9fc;
  border: 1px solid #d3dae3;
  font-family: 'Courier New', monospace;
  font-size: 12px;
  white-space: pre-wrap;
  word-break: break-all;
}

.note {
  margin: 0 0 8px;
  font-size: 12.5px;
  color: #6b7686;
}
</style>
