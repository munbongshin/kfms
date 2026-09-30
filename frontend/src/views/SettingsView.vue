<template>
  <div class="settings-view">
    <div class="page-title">
      <h2>LLM 설정</h2>
      <span v-if="saved" class="in-use">
        현재 사용 중:
        <strong>{{ platformOf(saved.provider)?.label }}</strong>
        · {{ platformOf(saved.provider)?.model || '모델 없음' }}
        <em v-if="saved.source === 'env'">(.env 기본값)</em>
      </span>
    </div>

    <p class="notice">
      질문을 SQL로 바꿀 LLM 서빙 플랫폼을 고릅니다. 저장하면 <strong>다음 질문부터 바로 적용</strong>되며,
      서버를 다시 시작할 필요가 없습니다. 플랫폼마다 설정이 따로 저장되어 바꿔 가며 쓸 수 있습니다.
    </p>

    <div v-loading="loading" class="panel">
      <div class="section-title">서빙 플랫폼</div>
      <div class="platforms">
        <label
          v-for="p in platforms"
          :key="p.name"
          class="platform"
          :class="{ selected: provider === p.name }"
        >
          <input v-model="provider" type="radio" :value="p.name" />
          <div>
            <div class="p-name">
              {{ p.label }}
              <span v-if="saved?.provider === p.name" class="badge">사용 중</span>
              <span v-if="p.external" class="badge ext">외부</span>
            </div>
            <div class="p-desc">{{ p.description }}</div>
          </div>
        </label>
      </div>

      <template v-if="active && draft">
        <el-alert
          v-if="leavesNetwork"
          type="warning"
          :closable="false"
          show-icon
          class="external"
          title="외부 인터넷 서비스입니다. 질문과 테이블·컬럼 구조(한글명 포함)가 외부로 전송됩니다. 실제 거래 데이터 값은 전송되지 않습니다."
        />

        <div class="section-title">{{ active.label }} 설정</div>
        <p class="hint">{{ active.hint }}</p>

        <div class="fields">
          <label class="lbl">서버 주소</label>
          <div class="ctl">
            <el-input
              v-model="draft.base_url"
              :disabled="active.fixed_base_url"
              :placeholder="active.default_base_url || 'http://서버:포트/v1'"
              style="width: 380px"
              @change="loadModels"
            />
            <button
              v-if="!active.fixed_base_url && active.default_base_url && draft.base_url !== active.default_base_url"
              class="link"
              @click="draft.base_url = active.default_base_url"
            >
              기본값
            </button>
          </div>

          <template v-if="active.api_key !== 'none'">
            <label class="lbl">
              API 키
              <small v-if="active.api_key === 'optional'">(선택)</small>
            </label>
            <div class="ctl">
              <el-input
                v-model="draft.api_key"
                type="password"
                show-password
                autocomplete="new-password"
                :placeholder="active.api_key_set ? `저장된 키 ${active.api_key_hint} — 바꿀 때만 입력` : active.api_key === 'required' ? 'API 키 입력' : '서버가 키를 요구할 때만 입력'"
                style="width: 380px"
              />
              <button v-if="active.api_key_set && !draft.clear_api_key" class="link" @click="draft.clear_api_key = true">
                저장된 키 삭제
              </button>
              <span v-if="draft.clear_api_key" class="field-warn">
                저장하면 키가 삭제됩니다
                <button class="link" @click="draft.clear_api_key = false">취소</button>
              </span>
              <div class="field-hint">키는 암호화되어 저장되고, 화면으로는 다시 보내지 않습니다.</div>
            </div>
          </template>

          <label class="lbl">모델</label>
          <div class="ctl">
            <el-select
              v-model="draft.model"
              filterable
              allow-create
              default-first-option
              placeholder="모델 선택 또는 입력"
              style="width: 380px"
              :loading="modelsLoading"
            >
              <el-option v-for="m in models" :key="m" :label="m" :value="m" />
            </el-select>
            <button class="link" :disabled="modelsLoading" @click="loadModels">목록 불러오기</button>
            <div v-if="modelsError" class="field-error">{{ modelsError }}</div>
            <div v-else-if="models.length" class="field-hint">
              서버에서 쓸 수 있는 모델 {{ models.length }}개 · 임베딩 전용 모델(embed, bge 등)은 SQL 생성에 쓸 수 없습니다
            </div>
          </div>
        </div>
      </template>

      <div v-if="testResult" class="test-result" :class="testResult.ok ? 'ok' : 'fail'">
        <el-icon><CircleCheckFilled v-if="testResult.ok" /><WarningFilled v-else /></el-icon>
        <span>{{ testResult.message }}</span>
        <small v-if="testResult.elapsed_ms != null">{{ testResult.elapsed_ms }}ms</small>
      </div>

      <div class="actions">
        <button class="btn" :disabled="testing || saving" @click="runTest">
          {{ testing ? '확인 중…' : '연결 테스트' }}
        </button>
        <button class="btn primary" :disabled="saving || testing || !dirty" @click="save">
          {{ saving ? '저장 중…' : '저장' }}
        </button>
        <button v-if="dirty" class="link" @click="reset">변경 취소</button>
      </div>
    </div>

    <!-- Business glossary -->
    <div class="panel glossary">
      <div class="section-title">업무 용어집</div>
      <p class="hint">
        질문에 용어가 들어 있으면 뜻을 LLM에 함께 알려 줍니다. 예: <b>고액</b> = 한 건 결제금액이 50만원 이상.
        같은 용어는 항상 같은 조건으로 해석됩니다.
      </p>
      <div class="term-form">
        <el-input v-model="newTerm" placeholder="용어 (예: 고액)" style="width: 180px" />
        <el-input v-model="newDefinition" placeholder="뜻 (예: 한 건 결제금액이 50만원 이상)" style="flex: 1" @keyup.enter="addTerm" />
        <button class="btn primary" :disabled="!newTerm.trim() || !newDefinition.trim()" @click="addTerm">
          {{ editingId ? '수정 저장' : '추가' }}
        </button>
        <button v-if="editingId" class="link" @click="cancelEdit">취소</button>
      </div>
      <el-table :data="terms" size="small" border empty-text="등록된 용어가 없습니다" style="margin-top: 10px">
        <el-table-column prop="term" label="용어" width="180" />
        <el-table-column prop="definition" label="뜻" show-overflow-tooltip />
        <el-table-column label="" width="130" align="center">
          <template #default="{ row }">
            <button class="link" @click="editTerm(row)">수정</button>
            <el-popconfirm title="이 용어를 삭제할까요?" @confirm="removeTerm(row.id)">
              <template #reference><button class="link danger">삭제</button></template>
            </el-popconfirm>
          </template>
        </el-table-column>
      </el-table>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { CircleCheckFilled, WarningFilled } from '@element-plus/icons-vue'
import {
  api,
  type GlossaryTerm,
  type LLMPlatform,
  type LLMProviderName,
  type LLMSettings,
  type LLMSettingsUpdate,
  type LLMTestResult,
} from '../services/api'

interface Draft {
  base_url: string
  model: string
  api_key: string
  clear_api_key: boolean
}

// --- business glossary ---
const terms = ref<GlossaryTerm[]>([])
const newTerm = ref('')
const newDefinition = ref('')
const editingId = ref<number | null>(null)

async function loadTerms() {
  try {
    terms.value = await api.glossary.list()
  } catch {
    ElMessage.error('용어집을 불러오지 못했습니다')
  }
}

async function addTerm() {
  const term = newTerm.value.trim()
  const definition = newDefinition.value.trim()
  if (!term || !definition) return
  try {
    if (editingId.value) await api.glossary.update(editingId.value, term, definition)
    else await api.glossary.create(term, definition)
    cancelEdit()
    await loadTerms()
  } catch (error: any) {
    ElMessage.error(error.response?.data?.detail || '저장하지 못했습니다')
  }
}

function editTerm(row: GlossaryTerm) {
  editingId.value = row.id
  newTerm.value = row.term
  newDefinition.value = row.definition
}

function cancelEdit() {
  editingId.value = null
  newTerm.value = ''
  newDefinition.value = ''
}

async function removeTerm(id: number) {
  try {
    await api.glossary.remove(id)
    await loadTerms()
  } catch {
    ElMessage.error('삭제하지 못했습니다')
  }
}

const saved = ref<LLMSettings | null>(null)
const provider = ref<LLMProviderName>('ollama')
// One draft per platform, so switching cards keeps what was typed.
const drafts = ref<Partial<Record<LLMProviderName, Draft>>>({})

const loading = ref(false)
const saving = ref(false)
const testing = ref(false)
const testResult = ref<LLMTestResult | null>(null)

const models = ref<string[]>([])
const modelsLoading = ref(false)
const modelsError = ref('')

const platforms = computed(() => saved.value?.platforms || [])
const active = computed(() => platformOf(provider.value))
const draft = computed(() => drafts.value[provider.value])

function platformOf(name: string): LLMPlatform | undefined {
  return platforms.value.find((p) => p.name === name)
}

/** Only addresses outside the private network warrant the warning. */
const PRIVATE_HOST = /^(localhost|127\.|10\.|192\.168\.|172\.(1[6-9]|2\d|3[01])\.|\[?::1\]?)/

const leavesNetwork = computed(() => {
  if (!active.value || !draft.value) return false
  if (active.value.external) return true
  try {
    return !PRIVATE_HOST.test(new URL(draft.value.base_url).hostname)
  } catch {
    return false
  }
})

function fill(s: LLMSettings) {
  saved.value = s
  provider.value = s.provider
  drafts.value = Object.fromEntries(
    s.platforms.map((p) => [p.name, { base_url: p.base_url, model: p.model, api_key: '', clear_api_key: false }])
  )
}

function changed(p: LLMPlatform): boolean {
  const d = drafts.value[p.name]
  return !!d && (d.base_url !== p.base_url || d.model !== p.model || d.api_key !== '' || d.clear_api_key)
}

const dirty = computed(
  () => !!saved.value && (provider.value !== saved.value.provider || platforms.value.some(changed))
)

/** The chosen platform plus every platform the user edited. */
function payload(): LLMSettingsUpdate {
  const profiles: LLMSettingsUpdate['profiles'] = {}
  for (const p of platforms.value) {
    const d = drafts.value[p.name]
    if (!d || (p.name !== provider.value && !changed(p))) continue
    profiles[p.name] = {
      base_url: d.base_url,
      model: d.model,
      // Blank means "keep the stored key" on the server.
      api_key: d.api_key,
      clear_api_key: d.clear_api_key,
    }
  }
  return { provider: provider.value, profiles }
}

async function loadModels() {
  if (!draft.value?.base_url) return
  modelsLoading.value = true
  modelsError.value = ''
  try {
    models.value = await api.llmSettings.models(payload())
  } catch (error: any) {
    models.value = []
    modelsError.value = error.response?.data?.detail || '모델 목록을 받지 못했습니다'
  } finally {
    modelsLoading.value = false
  }
}

async function runTest() {
  testing.value = true
  testResult.value = null
  try {
    testResult.value = await api.llmSettings.test(payload())
    if (testResult.value.models?.length) models.value = testResult.value.models
  } catch (error: any) {
    testResult.value = { ok: false, message: error.response?.data?.detail || '테스트하지 못했습니다' }
  } finally {
    testing.value = false
  }
}

async function save() {
  saving.value = true
  try {
    fill(await api.llmSettings.save(payload()))
    ElMessage.success('LLM 설정을 저장했습니다. 다음 질문부터 적용됩니다.')
  } catch (error: any) {
    ElMessage.error(error.response?.data?.detail || '저장하지 못했습니다')
  } finally {
    saving.value = false
  }
}

function reset() {
  if (saved.value) fill(saved.value)
  testResult.value = null
}

// Another platform: its own model list and its own test result.
watch(provider, () => {
  testResult.value = null
  models.value = []
  modelsError.value = ''
  loadModels()
})

onMounted(async () => {
  loadTerms()
  loading.value = true
  try {
    fill(await api.llmSettings.get())
  } catch {
    ElMessage.error('LLM 설정을 불러오지 못했습니다')
  } finally {
    loading.value = false
  }
  loadModels()
})
</script>

<style scoped>
.settings-view {
  max-width: 980px;
}

.page-title {
  display: flex;
  align-items: baseline;
  gap: 16px;
  margin-bottom: 6px;
}

.page-title h2 {
  margin: 0;
  padding-left: 10px;
  border-left: 4px solid #1b3c74;
  font-size: 18px;
  color: #1b3c74;
}

.in-use {
  font-size: 13px;
  color: #475467;
}

.in-use strong {
  color: #1a5fa8;
}

.in-use em {
  font-style: normal;
  color: #8a94a3;
}

.notice {
  margin: 0 0 12px;
  font-size: 13px;
  color: #475467;
}

.panel {
  padding: 18px 22px 20px;
  background: #fff;
  border: 1px solid #d3dae3;
}

.section-title {
  margin: 4px 0 10px;
  font-size: 14px;
  font-weight: 700;
  color: #1f3a66;
}

.section-title:not(:first-child) {
  margin-top: 20px;
}

.platforms {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(175px, 1fr));
  gap: 8px;
}

.platform {
  display: flex;
  gap: 8px;
  align-items: flex-start;
  padding: 10px 12px;
  border: 1px solid #d3dae3;
  background: #f9fbfd;
  cursor: pointer;
}

.platform.selected {
  border-color: #1a5fa8;
  background: #eef3fa;
  box-shadow: inset 3px 0 0 #1a5fa8;
}

.platform input {
  margin-top: 3px;
}

.p-name {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 4px;
  font-weight: 700;
  color: #1b3c74;
}

.badge {
  padding: 0 6px;
  border-radius: 8px;
  background: #e0ecfa;
  color: #1a5fa8;
  font-size: 11px;
  font-weight: 600;
}

.badge.ext {
  background: #fff4e0;
  color: #b54708;
}

.p-desc {
  margin-top: 3px;
  font-size: 12px;
  line-height: 1.45;
  color: #6b7686;
}

.external {
  margin-top: 12px;
}

.hint {
  margin: -4px 0 12px;
  font-size: 12.5px;
  color: #6b7686;
}

.fields {
  display: grid;
  grid-template-columns: 90px 1fr;
  row-gap: 12px;
  align-items: start;
}

.lbl {
  padding-top: 6px;
  font-size: 13px;
  font-weight: 600;
  color: #344054;
}

.lbl small {
  font-weight: 400;
  color: #8a94a3;
}

.ctl {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 10px;
}

.field-hint,
.field-error {
  flex-basis: 100%;
  font-size: 12px;
  color: #8a94a3;
}

.field-error {
  color: #b42318;
}

.field-warn {
  font-size: 12px;
  color: #b54708;
}

.test-result {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 18px;
  padding: 9px 12px;
  font-size: 13px;
  border-left: 3px solid;
}

.test-result.ok {
  background: #ecfdf3;
  border-color: #12b76a;
  color: #05603a;
}

.test-result.fail {
  background: #fef3f2;
  border-color: #f04438;
  color: #b42318;
}

.test-result small {
  margin-left: auto;
  color: #6b7686;
}

.actions {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 18px;
  padding-top: 14px;
  border-top: 1px solid #edf0f4;
}

.btn {
  height: 30px;
  padding: 0 16px;
  border: 1px solid #b8c3d3;
  background: #fff;
  color: #344054;
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
  color: #1a5fa8;
  font-size: 12.5px;
  text-decoration: underline;
  cursor: pointer;
}

.glossary {
  margin-top: 16px;
}

.term-form {
  display: flex;
  gap: 8px;
  align-items: center;
}

.link.danger {
  margin-left: 10px;
  color: #b42318;
}

.link:disabled {
  color: #98a2b3;
  cursor: not-allowed;
}
</style>
