<template>
  <el-dialog
    :model-value="modelValue"
    title="적용되는 공휴일"
    width="640px"
    append-to-body
    @update:model-value="emit('update:modelValue', $event)"
    @open="onOpen"
  >
    <!-- Where the list comes from, and whether a newly announced holiday has been picked up -->
    <section class="status">
      <div class="line">
        <span class="k">내장 달력</span>
        <span>holidays {{ status?.package_version || '—' }} <small>(설날·추석·대체공휴일 자동 계산)</small></span>
      </div>
      <div class="line">
        <span class="k">동기화</span>
        <span v-if="status?.last_synced_at">
          {{ fmt(status.last_synced_at) }} ·
          <b :class="status.last_status">{{ statusText }}</b>
          <template v-if="status.last_source"> · 출처 {{ SOURCE_NAMES[status.last_source] || status.last_source }}</template>
          · 받은 공휴일 {{ status.synced_count }}일
        </span>
        <span v-else class="muted">아직 동기화한 적이 없습니다 (하루에 한 번 자동으로 받아 옵니다)</span>
      </div>
      <p v-if="status?.last_error" class="err">{{ status.last_error }}</p>
      <div class="actions">
        <el-button size="small" :loading="syncing" @click="syncNow">지금 동기화</el-button>
        <el-button v-if="auth.isAdmin" size="small" @click="openKey">
          공식 서비스키 {{ status?.key_saved ? '(저장됨)' : '설정' }}
        </el-button>
        <span class="hint">
          {{ status?.key_saved ? '공식(공공데이터포털)을 먼저 쓰고, 실패하면 구글 캘린더로 대신합니다' : '서비스키가 없어 구글 공개 캘린더에서 받습니다' }}
        </span>
      </div>
    </section>

    <!-- Is this date counted? -->
    <section class="check">
      <strong>날짜 확인</strong>
      <el-date-picker v-model="checkDate" type="date" value-format="YYYY-MM-DD" size="small" placeholder="날짜 선택" style="width: 160px" />
      <el-button size="small" type="primary" :disabled="!checkDate" :loading="checking" @click="checkOne">확인</el-button>
      <div v-if="answer" class="answer" :class="answer.holiday ? 'yes' : 'no'">
        <div>
          <b>{{ answer.date }} ({{ answer.weekday }})</b>
          — {{ answer.message }}
        </div>
        <div v-if="answer.reason === 'not_found' || answer.reason === 'excluded'" class="answer-actions">
          <el-button v-if="answer.reason === 'not_found'" size="small" @click="addExtra">추가 공휴일로 등록</el-button>
          <el-button v-if="answer.reason === 'excluded'" size="small" @click="undoException">제외 취소</el-button>
        </div>
      </div>
    </section>

    <div class="year">
      <el-button size="small" :disabled="year <= 2000" @click="move(-1)">◀</el-button>
      <strong>{{ year }}년</strong>
      <el-button size="small" :disabled="year >= 2100" @click="move(1)">▶</el-button>
      <el-checkbox v-model="onlyTemporary" size="small">임시공휴일·새로 반영된 날만</el-checkbox>
      <span class="total">{{ activeCount }}일</span>
    </div>

    <el-table v-loading="loading" :data="shownRows" size="small" border max-height="300" empty-text="해당하는 공휴일이 없습니다">
      <el-table-column label="날짜" width="150">
        <template #default="{ row }">
          <span :class="{ struck: row.excluded }">{{ row.date }} ({{ weekday(row.date) }})</span>
        </template>
      </el-table-column>
      <el-table-column label="이름" min-width="150">
        <template #default="{ row }">
          <span :class="{ struck: row.excluded }">{{ row.name || '(이름 없음)' }}</span>
          <el-tag v-if="row.temporary" size="small" type="warning" effect="plain" class="ml">임시</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="구분" width="120" align="center">
        <template #default="{ row }">
          <el-tag v-if="row.excluded" size="small" type="danger">제외됨</el-tag>
          <el-tag v-else-if="row.source === 'extra'" size="small" type="success">추가</el-tag>
          <el-tag v-else-if="row.new" size="small" type="warning">새로 반영</el-tag>
          <el-tag v-else-if="row.source === 'synced'" size="small">동기화</el-tag>
          <el-tag v-else size="small" type="info">내장</el-tag>
        </template>
      </el-table-column>
    </el-table>

    <template #footer>
      <el-button @click="emit('update:modelValue', false)">닫기</el-button>
    </template>

    <el-dialog v-model="keyOpen" title="공공데이터포털 서비스키" width="460px" append-to-body>
      <p class="note">
        공공데이터포털(data.go.kr)에서 <b>한국천문연구원 특일 정보</b> 활용 신청 후 발급되는 무료 서비스키입니다.
        저장한 키는 암호화되고 화면에 다시 나타나지 않습니다. 비워서 저장하면 키를 지우고 구글 캘린더만 씁니다.
      </p>
      <el-input v-model="keyText" type="password" show-password placeholder="서비스키 (Encoding · Decoding 어느 것이나)" autocomplete="off" />
      <template #footer>
        <el-button @click="keyOpen = false">취소</el-button>
        <el-button type="primary" :loading="savingKey" @click="saveKey">저장</el-button>
      </template>
    </el-dialog>
  </el-dialog>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { api } from '../../services/api'
import { useAuthStore } from '../../stores/auth'

const props = defineProps<{
  modelValue: boolean
  autoHolidays: boolean
  holidays: string[]
  exceptions: string[]
}>()
const emit = defineEmits<{
  'update:modelValue': [value: boolean]
  'add-extra': [date: string]
  'remove-exception': [date: string]
}>()

interface Row {
  date: string
  name: string
  source: 'auto' | 'synced' | 'extra'
  excluded: boolean
  new: boolean
  temporary: boolean
}
interface Status {
  key_saved: boolean
  last_synced_at: string | null
  last_status: 'ok' | 'partial' | 'error' | null
  last_error: string | null
  last_source: string | null
  synced_count: number
  package_version: string
}
interface Answer {
  date: string
  weekday: string
  holiday: boolean
  reason: string
  message: string
}

const SOURCE_NAMES: Record<string, string> = { official: '공식(공공데이터포털)', google: '구글 캘린더' }

const auth = useAuthStore()
const year = ref(new Date().getFullYear())
const rows = ref<Row[]>([])
const loading = ref(false)
const onlyTemporary = ref(false)
const status = ref<Status | null>(null)
const syncing = ref(false)
const checkDate = ref('')
const checking = ref(false)
const answer = ref<Answer | null>(null)
const keyOpen = ref(false)
const keyText = ref('')
const savingKey = ref(false)

const DAYS = ['일', '월', '화', '수', '목', '금', '토']
const weekday = (iso: string) => DAYS[new Date(`${iso}T00:00:00Z`).getUTCDay()]
const fmt = (iso: string) => new Date(iso).toLocaleString('ko-KR')
const shownRows = computed(() => (onlyTemporary.value ? rows.value.filter((r) => r.temporary || r.new) : rows.value))
const activeCount = computed(() => shownRows.value.filter((r) => !r.excluded).length)
const statusText = computed(() =>
  status.value?.last_status === 'ok' ? '성공' : status.value?.last_status === 'partial' ? '일부만 성공' : '실패'
)

function settings() {
  return { auto_holidays: props.autoHolidays, holidays: props.holidays, holiday_exceptions: props.exceptions }
}

async function load() {
  loading.value = true
  try {
    rows.value = (await api.anomaly.holidayPreview({ year: year.value, ...settings() })).holidays
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || '공휴일을 불러오지 못했습니다')
    rows.value = []
  } finally {
    loading.value = false
  }
}

async function loadStatus() {
  try {
    status.value = await api.anomaly.holidayStatus()
  } catch {
    status.value = null
  }
}

function onOpen() {
  year.value = new Date().getFullYear()
  answer.value = null
  load()
  loadStatus()
}

function move(step: number) {
  year.value += step
  load()
}

async function syncNow() {
  syncing.value = true
  try {
    status.value = await api.anomaly.holidaySync()
    await load()
    if (status.value?.last_status === 'ok') ElMessage.success('공휴일을 새로 받아 왔습니다')
    else ElMessage.warning(status.value?.last_error || '동기화하지 못했습니다')
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || '동기화하지 못했습니다')
  } finally {
    syncing.value = false
  }
}

async function checkOne() {
  checking.value = true
  try {
    answer.value = await api.anomaly.holidayCheck({ date: checkDate.value, ...settings() })
    const y = Number(checkDate.value.slice(0, 4))
    if (y !== year.value) {
      year.value = y
      await load()
    }
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || '확인하지 못했습니다')
  } finally {
    checking.value = false
  }
}

function addExtra() {
  emit('add-extra', checkDate.value)
  ElMessage.success('추가 공휴일에 넣었습니다 (저장하면 적용됩니다)')
}

function undoException() {
  emit('remove-exception', checkDate.value)
  ElMessage.success('제외를 취소했습니다 (저장하면 적용됩니다)')
}

function openKey() {
  keyText.value = ''
  keyOpen.value = true
}

async function saveKey() {
  savingKey.value = true
  try {
    status.value = await api.anomaly.holidayKey(keyText.value)
    keyOpen.value = false
    ElMessage.success(keyText.value.trim() ? '서비스키를 저장했습니다. 지금 동기화로 확인해 보세요.' : '서비스키를 지웠습니다')
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || '저장하지 못했습니다')
  } finally {
    savingKey.value = false
  }
}

// The lists may change while this is open (a date was just added); keep it in step.
watch(() => [props.autoHolidays, props.holidays, props.exceptions], () => {
  if (!props.modelValue) return
  load()
  if (checkDate.value && answer.value) checkOne()
}, { deep: true })
</script>

<style scoped>
.status {
  margin-bottom: 12px;
  padding: 8px 12px;
  border: 1px solid #d3dae3;
  background: #f9fbfd;
  font-size: 13px;
  line-height: 1.7;
}

.line {
  display: flex;
  gap: 10px;
}

.k {
  flex: 0 0 64px;
  font-weight: 600;
  color: #344054;
}

.status small,
.muted {
  color: #8a94a3;
}

.status b.ok {
  color: #067647;
}

.status b.partial {
  color: #b54708;
}

.status b.error {
  color: #b42318;
}

.err {
  margin: 2px 0 0 74px;
  font-size: 12px;
  color: #b42318;
}

.actions {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 6px;
}

.hint {
  font-size: 12px;
  color: #8a94a3;
}

.check {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 12px;
  font-size: 13px;
}

.answer {
  flex-basis: 100%;
  padding: 8px 12px;
  border-radius: 3px;
  font-size: 13px;
  line-height: 1.6;
}

.answer.yes {
  background: #ecfdf3;
  border-left: 3px solid #12b76a;
}

.answer.no {
  background: #fff8ec;
  border-left: 3px solid #f79009;
}

.answer-actions {
  margin-top: 6px;
}

.year {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 8px;
}

.total {
  margin-left: auto;
  font-size: 12.5px;
  color: #667085;
}

.struck {
  color: #a0a8b5;
  text-decoration: line-through;
}

.ml {
  margin-left: 6px;
}

.note {
  margin: 0 0 10px;
  font-size: 13px;
  line-height: 1.6;
  color: #475467;
}
</style>
