<template>
  <div class="eval">
    <p
      class="intro"
      v-html="$th('질문과 <b>정답 SQL</b>을 저장해 두고, 지금 선택한 LLM이 같은 결과를 내는지 자동으로 채점합니다. LLM이나 모델을 바꿀 때 정확도가 좋아졌는지 나빠졌는지 바로 비교할 수 있습니다. 채점은 <b>실행 결과</b>가 같은지로 하므로 컬럼 이름·순서나 행 순서가 달라도 맞으면 정답입니다. 채점하는 동안에는 북마크 예시를 쓰지 않습니다(정답이 그대로 들어가기 때문입니다).')"
    ></p>

    <div class="bar">
      <span class="db" v-html="$th('대상 DB: <b>{name}</b>', { name: databaseStore.activeConnection?.name || t('없음') })"></span>
      <button class="btn" :disabled="!database" @click="importBookmarks">{{ $t('북마크에서 가져오기') }}</button>
      <button class="btn primary" :disabled="!database || !cases.length || running" @click="start">
        {{ running ? $t('채점 중…') : $t('평가 실행 ({n}건)', { n: cases.length }) }}
      </button>
    </div>

    <!-- Live / latest run -->
    <div v-if="shown" class="run">
      <div class="run-head">
        <span class="rate" :class="rateClass">{{ rate }}%</span>
        <span>{{ $t('{passed} / {total} 정답', { passed: shown.passed, total: shown.total }) }}</span>
        <span class="muted">· {{ shown.provider || '…' }} {{ shown.model }}</span>
        <span v-if="shown.status === 'running'" class="muted">· {{ $t('진행 {done} / {total}', { done: shown.done, total: shown.total }) }}</span>
        <span v-if="shown.seconds" class="muted">· {{ $t('{n}초', { n: shown.seconds }) }}</span>
        <el-tag v-if="shown.status === 'error'" type="danger" size="small">{{ $t('오류') }}</el-tag>
      </div>
      <el-progress v-if="shown.status === 'running'" :percentage="Math.round((shown.done / Math.max(shown.total, 1)) * 100)" :stroke-width="6" />
      <el-alert v-if="shown.error" type="error" :closable="false" show-icon :title="shown.error" />

      <el-table v-if="details.length" :data="details" size="small" border style="margin-top: 8px">
        <el-table-column type="expand">
          <template #default="{ row }">
            <div class="sqls">
              <div><b>{{ $t('정답 SQL') }}</b><pre>{{ row.expected_sql }}</pre></div>
              <div><b>{{ $t('생성한 SQL') }}</b><pre>{{ row.generated_sql || $t('(생성 실패)') }}</pre></div>
            </div>
          </template>
        </el-table-column>
        <el-table-column :label="$t('결과')" width="80" align="center">
          <template #default="{ row }">
            <el-tag :type="row.passed ? 'success' : 'danger'" size="small">{{ row.passed ? $t('정답') : $t('오답') }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="question" :label="$t('질문')" min-width="240" show-overflow-tooltip />
        <el-table-column prop="reason" :label="$t('사유')" min-width="240" show-overflow-tooltip />
      </el-table>
    </div>

    <!-- History of runs -->
    <div class="section">{{ $t('실행 기록') }}</div>
    <el-table :data="runs" size="small" border :empty-text="$t('아직 채점한 기록이 없습니다')" @row-click="openRun">
      <el-table-column :label="$t('시각')" width="170">
        <template #default="{ row }">{{ fmt(row.started_at) }}</template>
      </el-table-column>
      <el-table-column label="LLM" min-width="200">
        <template #default="{ row }">{{ row.provider }} {{ row.model }}</template>
      </el-table-column>
      <el-table-column :label="$t('정확도')" width="150">
        <template #default="{ row }">
          <b>{{ row.total ? Math.round((row.passed * 1000) / row.total) / 10 : 0 }}%</b>
          <span class="muted"> ({{ row.passed }}/{{ row.total }})</span>
        </template>
      </el-table-column>
      <el-table-column :label="$t('시간')" width="90">
        <template #default="{ row }">{{ row.seconds ? $t('{n}초', { n: row.seconds }) : '—' }}</template>
      </el-table-column>
      <el-table-column :label="$t('상태')" width="90" align="center">
        <template #default="{ row }">
          <el-tag :type="row.status === 'done' ? 'success' : row.status === 'running' ? 'warning' : 'danger'" size="small">
            {{ { done: $t('완료'), running: $t('진행 중'), error: $t('오류') }[row.status as string] || row.status }}
          </el-tag>
        </template>
      </el-table-column>
    </el-table>

    <!-- Cases -->
    <div class="section">{{ $t('평가 사례') }} <span class="muted">({{ $t('{n}건', { n: cases.length }) }})</span></div>
    <div class="form">
      <el-input v-model="newQuestion" :placeholder="$t('질문 (예: 카테고리별 총 매출액을 보여줘)')" style="width: 320px" />
      <el-input v-model="newSql" type="textarea" :rows="2" :placeholder="$t('정답 SQL (SELECT)')" style="flex: 1; min-width: 300px" />
      <button class="btn primary" :disabled="!newQuestion.trim() || !newSql.trim() || !database" @click="addCase">{{ $t('사례 추가') }}</button>
    </div>
    <el-table :data="cases" size="small" border :empty-text="$t('사례가 없습니다. 북마크에서 가져오거나 직접 추가하세요.')" style="margin-top: 8px">
      <el-table-column prop="question" :label="$t('질문')" min-width="240" show-overflow-tooltip />
      <el-table-column prop="expected_sql" :label="$t('정답 SQL')" min-width="360" show-overflow-tooltip />
      <el-table-column label="" width="80" align="center">
        <template #default="{ row }">
          <el-popconfirm :title="$t('이 사례를 삭제할까요?')" @confirm="removeCase(row.id)">
            <template #reference><button class="link danger">{{ $t('삭제') }}</button></template>
          </el-popconfirm>
        </template>
      </el-table-column>
    </el-table>
  </div>
</template>

<script setup lang="ts">
import { formatDateTime, t } from '../../i18n'
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { api } from '../../services/api'
import { useDatabaseStore } from '../../stores/database'

const databaseStore = useDatabaseStore()
const database = computed(() => databaseStore.activeConnectionId)

const cases = ref<any[]>([])
const runs = ref<any[]>([])
const shown = ref<any>(null)
const details = computed<any[]>(() => shown.value?.details || [])
const newQuestion = ref('')
const newSql = ref('')
let timer: ReturnType<typeof setInterval> | undefined

const running = computed(() => shown.value?.status === 'running' || runs.value.some((r) => r.status === 'running'))
const rate = computed(() =>
  shown.value?.total ? Math.round((shown.value.passed * 1000) / shown.value.total) / 10 : 0
)
const rateClass = computed(() => (rate.value >= 80 ? 'good' : rate.value >= 50 ? 'mid' : 'bad'))
const fmt = (iso: string | null) => (iso ? formatDateTime(iso) : '—')

async function loadCases() {
  if (!database.value) return
  cases.value = await api.evaluation.cases(database.value)
}

async function loadRuns() {
  runs.value = await api.evaluation.runs()
}

async function poll() {
  if (!shown.value) return
  shown.value = await api.evaluation.run(shown.value.id)
  if (shown.value.status !== 'running') {
    clearInterval(timer)
    timer = undefined
    await loadRuns()
  }
}

function watchRun() {
  clearInterval(timer)
  timer = setInterval(() => poll().catch(() => {}), 3000)
}

async function start() {
  if (!database.value) return
  try {
    shown.value = await api.evaluation.start(database.value)
    watchRun()
    await loadRuns()
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || t('시작하지 못했습니다'))
  }
}

async function openRun(row: any) {
  shown.value = await api.evaluation.run(row.id)
  if (shown.value.status === 'running') watchRun()
}

async function importBookmarks() {
  if (!database.value) return
  const { added } = await api.evaluation.importBookmarks(database.value)
  ElMessage.success(added ? t('북마크 {n}건을 사례로 추가했습니다', { n: added }) : t('새로 추가할 북마크가 없습니다'))
  await loadCases()
}

async function addCase() {
  if (!database.value) return
  try {
    await api.evaluation.addCase(newQuestion.value.trim(), newSql.value.trim(), database.value)
    newQuestion.value = ''
    newSql.value = ''
    await loadCases()
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || t('추가하지 못했습니다'))
  }
}

async function removeCase(id: number) {
  await api.evaluation.removeCase(id)
  await loadCases()
}

watch(database, loadCases)

onMounted(async () => {
  await Promise.all([loadCases(), loadRuns()])
  const active = runs.value.find((r) => r.status === 'running')
  if (active) {
    shown.value = await api.evaluation.run(active.id)
    watchRun()
  } else if (runs.value.length) {
    shown.value = await api.evaluation.run(runs.value[0].id)
  }
})

onBeforeUnmount(() => clearInterval(timer))
</script>

<style scoped>
.intro {
  margin: 0 0 12px;
  font-size: 13px;
  line-height: 1.7;
  color: #475467;
}

.bar {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 12px;
}

.db {
  margin-right: auto;
  font-size: 13px;
  color: #475467;
}

.run {
  margin-bottom: 14px;
  padding: 12px 14px;
  background: #f9fbfd;
  border: 1px solid #d3dae3;
}

.run-head {
  display: flex;
  align-items: baseline;
  gap: 10px;
  margin-bottom: 6px;
  font-size: 13px;
}

.rate {
  font-size: 26px;
  font-weight: 800;
}

.rate.good {
  color: #067647;
}

.rate.mid {
  color: #b54708;
}

.rate.bad {
  color: #b42318;
}

.muted {
  color: #8a94a3;
  font-size: 12.5px;
}

.section {
  margin: 18px 0 8px;
  font-size: 14px;
  font-weight: 700;
  color: #1f3a66;
}

.form {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: flex-start;
}

.sqls {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
  padding: 4px 12px;
}

.sqls pre {
  margin: 4px 0 0;
  padding: 8px;
  background: #f7f9fc;
  border: 1px solid #e1e6ed;
  font-size: 12px;
  white-space: pre-wrap;
  word-break: break-all;
}

.btn {
  height: 30px;
  padding: 0 14px;
  border: 1px solid #b8c3d3;
  background: #fff;
  font-size: 13px;
  cursor: pointer;
}

.btn.primary {
  border-color: #1a5fa8;
  background: #1a5fa8;
  color: #fff;
}

.btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.link {
  padding: 0;
  border: none;
  background: none;
  font-size: 12.5px;
  text-decoration: underline;
  cursor: pointer;
}

.link.danger {
  color: #b42318;
}
</style>
