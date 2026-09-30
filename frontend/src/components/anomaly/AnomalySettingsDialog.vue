<template>
  <el-dialog
    :model-value="modelValue"
    title="점검 기준"
    width="720px"
    @update:model-value="emit('update:modelValue', $event)"
    @open="load"
  >
    <p class="intro">
      이상거래 점검이 쓰는 기준 값입니다.
      <template v-if="auth.isAdmin">바꾸면 <strong>다음 조회부터</strong> 적용됩니다. 이미 검토한 판정은 그대로 남고, 기준이 바뀌어 거래 내용이 달라진 건은 "검토 후 변경됨"으로 다시 표시됩니다.</template>
      <template v-else>기준은 관리자만 바꿀 수 있습니다.</template>
    </p>

    <div v-loading="loading">
      <section v-for="rule in rules" :key="rule.template" class="rule">
        <div class="rule-head">
          <span class="name">{{ rule.label }}</span>
          <span class="sev" :class="rule.severity">{{ rule.severity === 'high' ? '높음' : '보통' }}</span>
        </div>

        <div v-for="p in rule.params" :key="p.key" class="param">
          <label class="lbl">{{ p.label }}</label>
          <div class="ctl">
            <el-input-number
              v-if="p.kind === 'number'"
              v-model="draft[rule.template][p.key]"
              :min="p.unit === 'hour' ? 0 : p.unit === 'count' ? 2 : 1"
              :max="p.unit === 'hour' ? 23 : p.unit === 'count' ? 50 : 1000000000000"
              :step="p.unit === 'number' ? 10000 : 1"
              :disabled="!auth.isAdmin"
              controls-position="right"
            />
            <el-input
              v-else
              v-model="draft[rule.template][p.key]"
              type="textarea"
              :rows="4"
              :disabled="!auth.isAdmin"
              placeholder="한 줄에 하나씩"
              style="width: 320px"
            />
            <div class="meta">
              <span class="hint">{{ p.hint }}</span>
              <span v-if="changed(rule.template, p)" class="changed">
                기본값: {{ display(p.default) }}
                <button v-if="auth.isAdmin" class="link" @click="reset(rule.template, p)">되돌리기</button>
              </span>
            </div>
          </div>
        </div>
      </section>
    </div>

    <template #footer>
      <el-button @click="emit('update:modelValue', false)">{{ auth.isAdmin ? '취소' : '닫기' }}</el-button>
      <el-button v-if="auth.isAdmin" type="primary" :loading="saving" :disabled="!dirty" @click="save">저장</el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { api } from '../../services/api'
import { useAuthStore } from '../../stores/auth'

interface Param {
  key: string
  label: string
  hint: string
  kind: 'number' | 'list'
  unit: 'number' | 'hour' | 'count' | 'list'
  value: any
  default: any
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

/** Lists edit as one item per line; numbers as numbers. */
function toEditable(p: Param, value: any) {
  return p.kind === 'list' ? (value || []).join('\n') : value
}

function fromEditable(p: Param, value: any) {
  return p.kind === 'list'
    ? String(value || '').split('\n').map((s) => s.trim()).filter(Boolean)
    : value
}

function display(value: any) {
  return Array.isArray(value) ? `${value.length}개` : String(value)
}

function same(p: Param, value: any) {
  return JSON.stringify(fromEditable(p, value)) === JSON.stringify(p.default)
}

const changed = (template: string, p: Param) => !same(p, draft.value[template]?.[p.key])

const dirty = computed(() =>
  rules.value.some((r) =>
    r.params.some((p) => JSON.stringify(fromEditable(p, draft.value[r.template][p.key])) !== JSON.stringify(p.value))
  )
)

async function load() {
  loading.value = true
  try {
    const data = await api.anomaly.getSettings()
    rules.value = data.rules
    draft.value = Object.fromEntries(
      data.rules.map((r: Rule) => [r.template, Object.fromEntries(r.params.map((p) => [p.key, toEditable(p, p.value)]))])
    )
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || '점검 기준을 불러오지 못했습니다')
  } finally {
    loading.value = false
  }
}

function reset(template: string, p: Param) {
  draft.value[template][p.key] = toEditable(p, p.default)
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
    ElMessage.success('점검 기준을 저장했습니다. 다음 조회부터 적용됩니다.')
    emit('saved')
    emit('update:modelValue', false)
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || '저장하지 못했습니다')
  } finally {
    saving.value = false
  }
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

.rule-head {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
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

.param {
  display: grid;
  grid-template-columns: 120px 1fr;
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
</style>
