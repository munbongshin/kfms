<template>
  <el-dialog
    :model-value="modelValue"
    :title="$t('점검 기준')"
    width="760px"
    @update:model-value="emit('update:modelValue', $event)"
    @open="load"
  >
    <p class="intro">
      {{ $t('이상거래 점검이 쓰는 기준 값입니다.') }}
      <span
        v-if="auth.isAuditor"
        v-html="$th('바꾸면 <strong>다음 조회부터</strong> 적용됩니다. 이미 검토한 판정은 그대로 남고, 기준이 바뀌어 거래 내용이 달라진 건은 “검토 후 변경됨”으로 다시 표시됩니다. 바꾼 내용은 <em>변경 이력</em>에 남고 이전 값으로 되돌릴 수 있습니다.')"
      ></span>
      <template v-else>{{ $t('기준은 관리자와 감사담당만 바꿀 수 있습니다.') }}</template>
    </p>

    <div v-loading="loading">
      <section v-for="rule in rules" :key="rule.template" class="rule" :class="{ off: isOff(rule) }">
        <div class="rule-head">
          <span class="name">{{ rule.label }}</span>
          <span class="sev" :class="draft[rule.template].severity">{{ severityName(draft[rule.template].severity) }}</span>
          <span class="spacer" />
          <label class="mini">{{ $t('심각도') }}</label>
          <el-select
            v-model="draft[rule.template].severity"
            size="small"
            style="width: 90px"
            :disabled="!auth.isAuditor"
          >
            <el-option v-for="o in severityOptions(rule)" :key="o.value" :label="o.label" :value="o.value" />
          </el-select>
          <label class="mini">{{ $t('사용') }}</label>
          <el-switch v-model="draft[rule.template].enabled" size="small" :disabled="!auth.isAuditor" />
        </div>
        <p v-if="isOff(rule)" class="off-note">{{ $t('사용을 꺼서 이 규칙으로는 점검하지 않습니다. 아래 값은 다시 켤 때 쓰입니다.') }}</p>

        <div v-for="p in detailParams(rule)" :key="p.key" class="param">
          <label class="lbl">{{ p.label }}</label>
          <div class="ctl">
            <el-switch
              v-if="p.kind === 'switch'"
              v-model="draft[rule.template][p.key]"
              :disabled="!auth.isAuditor"
            />

            <el-input-number
              v-else-if="p.kind === 'number'"
              v-model="draft[rule.template][p.key]"
              :min="limits(p).min"
              :max="limits(p).max"
              :step="limits(p).step"
              :disabled="!auth.isAuditor"
              controls-position="right"
            />

            <div v-else-if="p.kind === 'map'" class="map">
              <div v-for="(row, i) in draft[rule.template][p.key]" :key="i" class="map-row">
                <el-autocomplete
                  v-model="row.name"
                  size="small"
                  :placeholder="$t('업종명')"
                  :disabled="!auth.isAuditor"
                  :fetch-suggestions="suggestCategory"
                  value-key="name"
                  :trigger-on-focus="false"
                  style="width: 200px"
                />
                <el-input-number
                  v-model="row.amount"
                  size="small"
                  :min="1"
                  :max="1000000000000"
                  :step="10000"
                  :disabled="!auth.isAuditor"
                  controls-position="right"
                />
                <span class="won">{{ $t('원 이상') }}</span>
                <button v-if="auth.isAuditor" class="link" @click="removeRow(rule.template, p.key, i)">{{ $t('삭제') }}</button>
              </div>
              <button v-if="auth.isAuditor" class="link add" @click="addRow(rule.template, p.key, rule)">{{ $t('+ 업종 추가') }}</button>
              <span v-if="!draft[rule.template][p.key].length" class="none">{{ $t('모든 업종이 위의 기준 금액을 씁니다') }}</span>
            </div>

            <TagListEditor
              v-else
              v-model="draft[rule.template][p.key]"
              :disabled="!auth.isAuditor"
              :placeholder="listPlaceholder(p)"
              :suggestions="p.key === 'watch_mcc' ? categories : []"
              :validate="p.unit === 'dates' ? checkDate : undefined"
            />

            <div class="meta">
              <span class="hint">{{ p.hint }}</span>
              <button v-if="p.key === 'auto_holidays'" class="link show" @click="showHolidays = true">{{ $t('적용되는 공휴일 보기') }}</button>
              <span v-if="changed(rule.template, p)" class="changed">
                {{ $t('기본값: {v}', { v: display(p) }) }}
                <button v-if="auth.isAuditor" class="link" @click="reset(rule.template, p)">{{ $t('되돌리기') }}</button>
              </span>
            </div>
          </div>
        </div>
      </section>
    </div>

    <template #footer>
      <el-button class="history-btn" @click="showHistory = true">{{ $t('변경 이력') }}</el-button>
      <el-button @click="emit('update:modelValue', false)">{{ auth.isAuditor ? $t('취소') : $t('닫기') }}</el-button>
      <el-button v-if="auth.isAuditor" type="primary" :loading="saving" :disabled="!dirty" @click="save">{{ $t('저장') }}</el-button>
    </template>
  </el-dialog>

  <!-- Beside, not inside, the settings dialog: two open dialogs stack fine, a nested one stays hidden. -->
  <AnomalyHistoryDialog v-model="showHistory" @restored="afterRestore" />
  <HolidayPreviewDialog
    v-model="showHolidays"
    :auto-holidays="draft.OFF_HOURS?.auto_holidays !== false"
    :holidays="draft.OFF_HOURS?.holidays || []"
    :exceptions="draft.OFF_HOURS?.holiday_exceptions || []"
    @add-extra="addHoliday"
    @remove-exception="dropException"
  />
</template>

<script setup lang="ts">
import { t } from '../../i18n'
import { computed, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { api } from '../../services/api'
import { useAuthStore } from '../../stores/auth'
import AnomalyHistoryDialog from './AnomalyHistoryDialog.vue'
import TagListEditor, { type Suggestion } from './TagListEditor.vue'
import HolidayPreviewDialog from './HolidayPreviewDialog.vue'
import { useDatabaseStore } from '../../stores/database'
import { isIsoDate } from '../../utils/listInput'

interface Param {
  key: string
  label: string
  hint: string
  kind: 'number' | 'list' | 'switch' | 'choice' | 'map'
  unit: string
  value: any
  default: any
  options?: { value: string; label: string }[]
}
interface Rule {
  template: string
  label: string
  severity: string
  params: Param[]
}

defineProps<{ modelValue: boolean }>()
const emit = defineEmits<{ 'update:modelValue': [value: boolean]; saved: [] }>()

const auth = useAuthStore()
const rules = ref<Rule[]>([])
const draft = ref<Record<string, Record<string, any>>>({})
const loading = ref(false)
const saving = ref(false)
const showHistory = ref(false)
const showHolidays = ref(false)
const databaseStore = useDatabaseStore()
// Merchant categories in the data: suggested while typing, and used to flag names that match nothing.
const categories = ref<Suggestion[]>([])

const checkDate = (item: string) => (isIsoDate(item) ? '' : t("'{item}'은(는) YYYY-MM-DD 형식의 날짜가 아닙니다", { item }))
const listPlaceholder = (p: Param) =>
  p.unit === 'dates' ? t('예: 2026-05-05') : p.key === 'watch_mcc' ? t('업종명 (예: 영화관)') : t('한 개씩 입력하고 Enter')

function suggestCategory(query: string, cb: (items: Suggestion[]) => void) {
  const q = query.trim().toLowerCase()
  cb(categories.value.filter((c) => !q || c.name.toLowerCase().includes(q)).slice(0, 30))
}

async function loadCategories() {
  const id = databaseStore.activeConnectionId
  if (!id) return
  try {
    categories.value = await api.anomaly.categories(String(id))
  } catch {
    categories.value = [] // only a help; typing still works
  }
}

const SEVERITY_NAMES: Record<string, string> = { high: '높음', medium: '보통', low: '낮음' }
const severityName = (s: string) => (SEVERITY_NAMES[s] ? t(SEVERITY_NAMES[s]) : s)

/** Each rule's own controls, minus the two shown in its header. */
const detailParams = (rule: Rule) => rule.params.filter((p) => p.key !== 'enabled' && p.key !== 'severity')
const severityOptions = (rule: Rule) => rule.params.find((p) => p.key === 'severity')?.options || []
const isOff = (rule: Rule) => draft.value[rule.template]?.enabled === false

function limits(p: Param) {
  switch (p.unit) {
    case 'hour': return { min: 0, max: 23, step: 1 }
    case 'count': return { min: 2, max: 50, step: 1 }
    case 'minutes': return { min: 0, max: 1440, step: 5 }
    case 'amount0': return { min: 0, max: 1000000000000, step: 10000 }
    default: return { min: 1, max: 1000000000000, step: 10000 }
  }
}

/** Lists edit as a list of items, tables as rows; the rest as they are. */
function toEditable(p: Param, value: any) {
  if (p.kind === 'list') return [...(value || [])]
  if (p.kind === 'map') return Object.entries(value || {}).map(([name, amount]) => ({ name, amount }))
  return value
}

function fromEditable(p: Param, value: any) {
  if (p.kind === 'list') return [...(value || [])]
  if (p.kind === 'map') {
    const out: Record<string, number> = {}
    for (const row of value || []) {
      const name = String(row.name || '').trim()
      if (name && row.amount) out[name] = row.amount
    }
    return out
  }
  return value
}

/** A stable form to compare: table keys in order. */
function normal(p: Param, value: any) {
  const v = fromEditable(p, value)
  return p.kind === 'map' ? JSON.stringify(Object.entries(v).sort(([a], [b]) => a.localeCompare(b))) : JSON.stringify(v)
}

function display(p: Param) {
  const value = p.default
  if (p.kind === 'switch') return value ? t('켜짐') : t('꺼짐')
  if (p.kind === 'map') return Object.keys(value || {}).length ? t('{n}개', { n: Object.keys(value).length }) : t('없음')
  return Array.isArray(value) ? t('{n}개', { n: value.length }) : String(value)
}

const changed = (template: string, p: Param) =>
  normal(p, draft.value[template]?.[p.key]) !== normal(p, toEditable(p, p.default))

const dirty = computed(() =>
  rules.value.some((r) => r.params.some((p) => normal(p, draft.value[r.template][p.key]) !== normal(p, toEditable(p, p.value))))
)

async function load() {
  loadCategories()
  loading.value = true
  try {
    const data = await api.anomaly.getSettings()
    rules.value = data.rules
    draft.value = Object.fromEntries(
      data.rules.map((r: Rule) => [r.template, Object.fromEntries(r.params.map((p) => [p.key, toEditable(p, p.value)]))])
    )
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || t('점검 기준을 불러오지 못했습니다'))
  } finally {
    loading.value = false
  }
}

function reset(template: string, p: Param) {
  draft.value[template][p.key] = toEditable(p, p.default)
}

function addRow(template: string, key: string, rule: Rule) {
  const threshold = draft.value[rule.template].threshold || 500000
  draft.value[template][key].push({ name: '', amount: threshold })
}

function removeRow(template: string, key: string, index: number) {
  draft.value[template][key].splice(index, 1)
}

async function save() {
  saving.value = true
  try {
    const overrides = Object.fromEntries(
      rules.value.map((r) => [
        r.template,
        Object.fromEntries(r.params.map((p) => [p.key, fromEditable(p, draft.value[r.template][p.key])])),
      ])
    )
    await api.anomaly.saveSettings(overrides)
    ElMessage.success(t('점검 기준을 저장했습니다. 다음 조회부터 적용됩니다.'))
    emit('saved')
    emit('update:modelValue', false)
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || t('저장하지 못했습니다'))
  } finally {
    saving.value = false
  }
}

/** The history dialog put an earlier state back; show it and refresh the findings. */
/** From the holiday check: a date the list lacks goes into the extra days. */
function addHoliday(day: string) {
  const list: string[] = draft.value.OFF_HOURS.holidays
  if (!list.includes(day)) list.push(day)
  list.sort()
}

function dropException(day: string) {
  draft.value.OFF_HOURS.holiday_exceptions = draft.value.OFF_HOURS.holiday_exceptions.filter((d: string) => d !== day)
}

async function afterRestore() {
  await load()
  emit('saved')
}
</script>

<style scoped>
.intro {
  margin: 0 0 12px;
  font-size: 13px;
  line-height: 1.6;
  color: #475467;
}

.rule {
  margin-bottom: 14px;
  padding: 10px 14px 12px;
  border: 1px solid #d3dae3;
  background: #f9fbfd;
}

.rule.off .param {
  opacity: 0.5;
}

.rule-head {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}

.spacer {
  flex: 1;
}

.mini {
  font-size: 12px;
  color: #667085;
}

.off-note {
  margin: 0 0 6px;
  font-size: 12px;
  color: #b54708;
}

.name {
  font-weight: 700;
  color: #1b3c74;
}

.sev {
  padding: 0 8px;
  border-radius: 10px;
  font-size: 12px;
  font-weight: 600;
}

.sev.high {
  background: #fde8e8;
  color: #b42318;
}

.sev.medium {
  background: #fff4e0;
  color: #b54708;
}

.sev.low {
  background: #eaf2fb;
  color: #1a5fa8;
}

.param {
  display: grid;
  grid-template-columns: 130px 1fr;
  gap: 10px;
  padding: 6px 0;
}

.lbl {
  padding-top: 6px;
  font-size: 13px;
  font-weight: 600;
  color: #344054;
}

.meta {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  margin-top: 4px;
  font-size: 12px;
}

.hint {
  color: #8a94a3;
}

.changed {
  color: #b54708;
}

.map-row {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 6px;
}

.won {
  font-size: 12px;
  color: #667085;
}

.none {
  margin-left: 10px;
  font-size: 12px;
  color: #8a94a3;
}

.link {
  padding: 0;
  margin-left: 6px;
  border: none;
  background: none;
  color: #1a5fa8;
  font-size: 12px;
  text-decoration: underline;
  cursor: pointer;
}

.link.add {
  margin-left: 0;
}

.link.show {
  margin-left: 0;
}

.history-btn {
  float: left;
}
</style>
