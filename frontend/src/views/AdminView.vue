<template>
  <div class="admin-view">
    <div class="page-title"><h2>관리</h2></div>

    <el-tabs v-model="tab" @tab-change="onTab">
      <!-- Users -->
      <el-tab-pane label="사용자" name="users">
        <div class="panel">
          <div class="form">
            <el-input v-model="form.username" placeholder="아이디" style="width: 150px" />
            <el-input v-model="form.display_name" placeholder="이름 (선택)" style="width: 150px" />
            <el-input v-model="form.password" type="password" show-password placeholder="비밀번호 (8자 이상)" style="width: 190px" autocomplete="new-password" />
            <el-select v-model="form.role" style="width: 150px">
              <el-option v-for="r in ROLES" :key="r.value" :label="r.label" :value="r.value" />
            </el-select>
            <button class="btn primary" :disabled="!canCreate" @click="createUser">사용자 추가</button>
          </div>
          <p class="hint">
            <b>관리자</b> 모든 설정·사용자 관리 · <b>감사담당</b> 질의·점검, 카드번호 전체 열람 ·
            <b>조회</b> 질의만 가능, 카드번호는 마스킹
          </p>

          <el-table :data="users" size="small" border style="margin-top: 8px">
            <el-table-column prop="username" label="아이디" width="140" />
            <el-table-column prop="display_name" label="이름" width="140" />
            <el-table-column label="역할" width="150">
              <template #default="{ row }">
                <el-select :model-value="row.role" size="small" @change="(v: Role) => change(row, { role: v })">
                  <el-option v-for="r in ROLES" :key="r.value" :label="r.label" :value="r.value" />
                </el-select>
              </template>
            </el-table-column>
            <el-table-column label="상태" width="90" align="center">
              <template #default="{ row }">
                <el-switch :model-value="row.is_active" size="small" @change="(v: boolean) => change(row, { is_active: v })" />
              </template>
            </el-table-column>
            <el-table-column label="마지막 로그인" min-width="160">
              <template #default="{ row }">{{ row.last_login_at ? fmt(row.last_login_at) : '—' }}</template>
            </el-table-column>
            <el-table-column label="" width="130" align="center">
              <template #default="{ row }">
                <button class="link" @click="resetPassword(row)">비밀번호 변경</button>
              </template>
            </el-table-column>
          </el-table>
        </div>
      </el-tab-pane>

      <!-- Accuracy evaluation -->
      <el-tab-pane label="정확도 평가" name="eval" lazy>
        <div class="panel"><EvalPanel /></div>
      </el-tab-pane>

      <!-- Audit log -->
      <el-tab-pane label="감사 로그" name="audit">
        <div class="panel">
          <div class="form">
            <el-input v-model="filter.username" placeholder="사용자" clearable style="width: 140px" />
            <el-select v-model="filter.action" placeholder="동작" clearable style="width: 190px">
              <el-option v-for="a in ACTIONS" :key="a.value" :label="a.label" :value="a.value" />
            </el-select>
            <el-select v-model="filter.days" style="width: 130px">
              <el-option :value="1" label="최근 1일" />
              <el-option :value="7" label="최근 7일" />
              <el-option :value="30" label="최근 30일" />
              <el-option :value="365" label="최근 1년" />
            </el-select>
            <button class="btn primary" @click="loadAudit">조회</button>
            <span class="count">{{ entries.length }}건</span>
          </div>

          <el-table :data="entries" size="small" border v-loading="loadingAudit" max-height="560" style="margin-top: 8px" empty-text="기록이 없습니다">
            <el-table-column label="시각" width="160">
              <template #default="{ row }">{{ fmt(row.at) }}</template>
            </el-table-column>
            <el-table-column prop="username" label="사용자" width="110" />
            <el-table-column label="동작" width="150">
              <template #default="{ row }">{{ actionLabel(row.action) }}</template>
            </el-table-column>
            <el-table-column prop="target" label="대상" min-width="200" show-overflow-tooltip />
            <el-table-column label="내용" min-width="280" show-overflow-tooltip>
              <template #default="{ row }">{{ summarize(row) }}</template>
            </el-table-column>
            <el-table-column prop="ip" label="IP" width="120" />
          </el-table>
        </div>
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { api, type AppUser, type AuditEntry, type Role } from '../services/api'
import EvalPanel from '../components/admin/EvalPanel.vue'

const ROLES: Array<{ value: Role; label: string }> = [
  { value: 'admin', label: '관리자' },
  { value: 'auditor', label: '감사담당' },
  { value: 'viewer', label: '조회' },
]

const ACTIONS = [
  { value: 'login', label: '로그인' },
  { value: 'login_failed', label: '로그인 실패' },
  { value: 'query_execute', label: '질의 실행' },
  { value: 'table_preview', label: '테이블 미리보기' },
  { value: 'request', label: '변경·열람 요청' },
  { value: 'user_create', label: '사용자 추가' },
  { value: 'user_change', label: '사용자 변경' },
  { value: 'setup', label: '최초 설정' },
]

const tab = ref('users')
const users = ref<AppUser[]>([])
const entries = ref<AuditEntry[]>([])
const loadingAudit = ref(false)
const form = ref({ username: '', display_name: '', password: '', role: 'viewer' as Role })
const filter = ref({ username: '', action: '', days: 7 })

const canCreate = computed(
  () => form.value.username.trim().length >= 2 && form.value.password.length >= 8
)

const fmt = (iso: string) => new Date(iso).toLocaleString()
const actionLabel = (a: string) => ACTIONS.find((x) => x.value === a)?.label || a

/** One readable line per entry, without dumping the raw detail. */
function summarize(row: AuditEntry): string {
  const d = row.detail || {}
  if (row.action === 'query_execute') return `${d.question || ''} — ${d.rows ?? '?'}행 · ${d.sql || ''}`
  if (row.action === 'table_preview') return `${d.offset ?? 0}행부터 ${d.limit ?? ''}행`
  if (row.action === 'request') return `응답 ${d.status}`
  if (row.action === 'user_change') return (d.changed || []).join(', ')
  if (row.action === 'user_create') return `역할 ${d.role}`
  return ''
}

async function loadUsers() {
  try {
    users.value = await api.users.list()
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || '사용자를 불러오지 못했습니다')
  }
}

async function loadAudit() {
  loadingAudit.value = true
  try {
    entries.value = await api.audit.list({
      username: filter.value.username.trim() || undefined,
      action: filter.value.action || undefined,
      days: filter.value.days,
      limit: 500,
    })
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || '감사 로그를 불러오지 못했습니다')
  } finally {
    loadingAudit.value = false
  }
}

function onTab(name: string | number) {
  if (name === 'audit') loadAudit()
}

async function createUser() {
  try {
    await api.users.create({ ...form.value, username: form.value.username.trim() })
    form.value = { username: '', display_name: '', password: '', role: 'viewer' }
    ElMessage.success('사용자를 추가했습니다')
    await loadUsers()
  } catch (e: any) {
    const detail = e.response?.data?.detail
    ElMessage.error(typeof detail === 'string' ? detail : '추가하지 못했습니다. 입력을 확인하세요.')
  }
}

async function change(row: AppUser, changes: Partial<{ role: Role; is_active: boolean; password: string }>) {
  try {
    await api.users.change(row.id, changes)
    ElMessage.success('변경했습니다')
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || '변경하지 못했습니다')
  }
  await loadUsers()
}

async function resetPassword(row: AppUser) {
  try {
    const { value } = await ElMessageBox.prompt(`${row.username}의 새 비밀번호 (8자 이상)`, '비밀번호 변경', {
      inputType: 'password',
      confirmButtonText: '변경',
      cancelButtonText: '취소',
      inputValidator: (v: string) => (v && v.length >= 8) || '8자 이상 입력하세요',
    })
    await change(row, { password: value })
  } catch {
    // cancelled
  }
}

onMounted(loadUsers)
</script>

<style scoped>
.admin-view {
  max-width: 1100px;
}

.page-title h2 {
  margin: 0 0 8px;
  padding-left: 10px;
  border-left: 4px solid #1b3c74;
  font-size: 18px;
  color: #1b3c74;
}

.panel {
  padding: 16px 18px;
  background: #fff;
  border: 1px solid #d3dae3;
}

.form {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
}

.hint {
  margin: 10px 0 0;
  font-size: 12.5px;
  color: #6b7686;
}

.count {
  margin-left: auto;
  font-size: 12.5px;
  font-weight: 600;
  color: #1a5fa8;
}

.btn {
  height: 30px;
  padding: 0 16px;
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
  color: #1a5fa8;
  font-size: 12.5px;
  text-decoration: underline;
  cursor: pointer;
}
</style>
