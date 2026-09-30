<template>
  <div class="database-manager">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>{{ $t('데이터베이스 연결') }}</span>
          <el-button v-if="auth.isAdmin" type="primary" @click="openCreate">
            <el-icon><Plus /></el-icon>
            {{ $t('연결 추가') }}
          </el-button>
        </div>
      </template>

      <el-table :data="databaseStore.connections" v-loading="databaseStore.loading">
        <el-table-column prop="name" :label="$t('이름')" width="180" />
        <el-table-column prop="host" :label="$t('호스트')" />
        <el-table-column prop="port" :label="$t('포트')" width="80" />
        <el-table-column prop="database" :label="$t('데이터베이스')" />
        <el-table-column prop="username" :label="$t('사용자')" width="120" />
        <el-table-column :label="$t('읽기 전용')" width="100">
          <template #default="{ row }">
            <el-tag :type="row.is_read_only ? 'success' : 'warning'" size="small">
              {{ row.is_read_only ? $t('예') : $t('아니오') }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column :label="$t('상태')" width="100">
          <template #default="{ row }">
            <el-tag :type="row.is_active ? 'success' : 'info'" size="small">
              {{ row.is_active ? $t('사용') : $t('중지') }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column v-if="auth.isAdmin" :label="$t('작업')" width="340" fixed="right">
          <template #default="{ row }">
            <el-button size="small" @click="openTargets(row)">
              {{ $t('분석 대상') }}
            </el-button>
            <el-button size="small" @click="openEdit(row)">
              <el-icon><Edit /></el-icon>
              {{ $t('수정') }}
            </el-button>
            <el-button size="small" @click="testConnection(row.id)">
              <el-icon><Connection /></el-icon>
              {{ $t('연결 테스트') }}
            </el-button>
            <el-popconfirm
              :title="$t('이 연결을 삭제할까요?')"
              :confirm-button-text="$t('삭제')"
              :cancel-button-text="$t('취소')"
              @confirm="deleteConnection(row.id)"
            >
              <template #reference>
                <el-button size="small" type="danger">
                  <el-icon><Delete /></el-icon>
                </el-button>
              </template>
            </el-popconfirm>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <AnalysisTargetsDialog v-model="showTargets" :connection="targetsFor" />

    <!-- Create / Edit Connection Dialog -->
    <el-dialog
      v-model="showCreateDialog"
      :title="editingId ? $t('연결 수정') : $t('데이터베이스 연결 추가')"
      width="600px"
    >
      <el-form :model="formData" label-width="120px">
        <el-form-item :label="$t('이름')">
          <el-input v-model="formData.name" :placeholder="$t('예: 법인카드 DB')" />
        </el-form-item>
        <el-form-item :label="$t('호스트')">
          <el-input v-model="formData.host" placeholder="localhost" />
        </el-form-item>
        <el-form-item :label="$t('포트')">
          <el-input-number v-model="formData.port" :min="1" :max="65535" />
        </el-form-item>
        <el-form-item :label="$t('데이터베이스')">
          <el-input v-model="formData.database" :placeholder="$t('예: retail')" />
        </el-form-item>
        <el-form-item :label="$t('사용자 이름')">
          <el-input v-model="formData.username" placeholder="postgres" />
        </el-form-item>
        <el-form-item :label="$t('비밀번호')">
          <el-input
            v-model="formData.password"
            type="password"
            :placeholder="editingId ? $t('바꿀 때만 입력 (비우면 그대로)') : $t('비밀번호를 입력하세요')"
            show-password
          />
        </el-form-item>
        <el-form-item :label="$t('읽기 전용')">
          <el-switch v-model="formData.is_read_only" />
          <span class="hint">{{ $t('안전을 위해 켜 두기를 권장합니다') }}</span>
        </el-form-item>
        <el-form-item :label="$t('사용')">
          <el-switch v-model="formData.is_active" />
        </el-form-item>
      </el-form>

      <template #footer>
        <el-button @click="showCreateDialog = false">{{ $t('취소') }}</el-button>
        <el-button type="primary" @click="submit" :loading="databaseStore.loading">
          {{ editingId ? $t('저장') : $t('추가') }}
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { Plus, Connection, Delete, Edit } from '@element-plus/icons-vue'
import { useDatabaseStore } from '../../stores/database'
import { useAuthStore } from '../../stores/auth'
import AnalysisTargetsDialog from './AnalysisTargetsDialog.vue'
import type {
  DatabaseConnection,
  DatabaseConnectionCreate,
  DatabaseConnectionUpdate,
} from '../../services/api'

const databaseStore = useDatabaseStore()
const auth = useAuthStore()

const showCreateDialog = ref(false)
const showTargets = ref(false)
const targetsFor = ref<DatabaseConnection | null>(null)

function openTargets(row: DatabaseConnection) {
  targetsFor.value = row
  showTargets.value = true
}
// The connection being edited; null while adding a new one.
const editingId = ref<number | null>(null)
let original: DatabaseConnection | null = null
const formData = ref<DatabaseConnectionCreate>({
  name: '',
  host: 'localhost',
  port: 5432,
  database: '',
  username: 'postgres',
  password: '',
  is_active: true,
  is_read_only: true,
})

function openCreate() {
  editingId.value = null
  original = null
  resetForm()
  showCreateDialog.value = true
}

function openEdit(row: DatabaseConnection) {
  editingId.value = row.id
  original = row
  // The password is never sent back to the browser; blank means "keep it".
  formData.value = {
    name: row.name,
    host: row.host,
    port: row.port,
    database: row.database,
    username: row.username,
    password: '',
    is_active: row.is_active,
    is_read_only: row.is_read_only,
  }
  showCreateDialog.value = true
}

/** Only what the user actually changed, so a rename stays a rename. */
function changedFields(): DatabaseConnectionUpdate {
  const form = formData.value
  const changes: DatabaseConnectionUpdate = {}
  if (!original) return changes
  if (form.name.trim() !== original.name) changes.name = form.name.trim()
  if (form.host !== original.host) changes.host = form.host
  if (form.port !== original.port) changes.port = form.port
  if (form.database !== original.database) changes.database = form.database
  if (form.username !== original.username) changes.username = form.username
  if (form.password) changes.password = form.password
  if (form.is_active !== original.is_active) changes.is_active = form.is_active
  if (form.is_read_only !== original.is_read_only) changes.is_read_only = form.is_read_only
  return changes
}

async function submit() {
  try {
    if (editingId.value) {
      const changes = changedFields()
      if (Object.keys(changes).length) {
        await databaseStore.updateConnection(editingId.value, changes)
      }
    } else {
      await databaseStore.createConnection(formData.value)
    }
    showCreateDialog.value = false
    resetForm()
  } catch (error) {
    // Error handled in store
  }
}

async function testConnection(connectionId: number) {
  await databaseStore.testConnection(connectionId)
}

async function deleteConnection(connectionId: number) {
  await databaseStore.deleteConnection(connectionId)
}

function resetForm() {
  formData.value = {
    name: '',
    host: 'localhost',
    port: 5432,
    database: '',
    username: 'postgres',
    password: '',
    is_active: true,
    is_read_only: true,
  }
}

// Fetch connections on mount
databaseStore.fetchConnections()
</script>

<style scoped>
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.hint {
  margin-left: 10px;
  color: #909399;
  font-size: 12px;
}
</style>
