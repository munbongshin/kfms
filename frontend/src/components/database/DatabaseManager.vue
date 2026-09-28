<template>
  <div class="database-manager">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>Database Connections</span>
          <el-button type="primary" @click="openCreate">
            <el-icon><Plus /></el-icon>
            Add Connection
          </el-button>
        </div>
      </template>

      <el-table :data="databaseStore.connections" v-loading="databaseStore.loading">
        <el-table-column prop="name" label="Name" width="180" />
        <el-table-column prop="host" label="Host" />
        <el-table-column prop="port" label="Port" width="80" />
        <el-table-column prop="database" label="Database" />
        <el-table-column prop="username" label="Username" width="120" />
        <el-table-column label="Read-Only" width="100">
          <template #default="{ row }">
            <el-tag :type="row.is_read_only ? 'success' : 'warning'" size="small">
              {{ row.is_read_only ? 'Yes' : 'No' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="Status" width="100">
          <template #default="{ row }">
            <el-tag :type="row.is_active ? 'success' : 'info'" size="small">
              {{ row.is_active ? 'Active' : 'Inactive' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="Actions" width="250" fixed="right">
          <template #default="{ row }">
            <el-button size="small" @click="openEdit(row)">
              <el-icon><Edit /></el-icon>
              수정
            </el-button>
            <el-button size="small" @click="testConnection(row.id)">
              <el-icon><Connection /></el-icon>
              Test
            </el-button>
            <el-popconfirm
              title="Delete this connection?"
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

    <!-- Create / Edit Connection Dialog -->
    <el-dialog
      v-model="showCreateDialog"
      :title="editingId ? '연결 수정' : 'Add Database Connection'"
      width="600px"
    >
      <el-form :model="formData" label-width="120px">
        <el-form-item label="Name">
          <el-input v-model="formData.name" placeholder="My Database" />
        </el-form-item>
        <el-form-item label="Host">
          <el-input v-model="formData.host" placeholder="localhost" />
        </el-form-item>
        <el-form-item label="Port">
          <el-input-number v-model="formData.port" :min="1" :max="65535" />
        </el-form-item>
        <el-form-item label="Database">
          <el-input v-model="formData.database" placeholder="mydatabase" />
        </el-form-item>
        <el-form-item label="Username">
          <el-input v-model="formData.username" placeholder="postgres" />
        </el-form-item>
        <el-form-item label="Password">
          <el-input
            v-model="formData.password"
            type="password"
            :placeholder="editingId ? '바꿀 때만 입력 (비우면 그대로)' : 'Enter password'"
            show-password
          />
        </el-form-item>
        <el-form-item label="Read-Only Mode">
          <el-switch v-model="formData.is_read_only" />
          <span class="hint">Recommended for safety</span>
        </el-form-item>
        <el-form-item label="Active">
          <el-switch v-model="formData.is_active" />
        </el-form-item>
      </el-form>

      <template #footer>
        <el-button @click="showCreateDialog = false">Cancel</el-button>
        <el-button type="primary" @click="submit" :loading="databaseStore.loading">
          {{ editingId ? '저장' : 'Create' }}
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { Plus, Connection, Delete, Edit } from '@element-plus/icons-vue'
import { useDatabaseStore } from '../../stores/database'
import type {
  DatabaseConnection,
  DatabaseConnectionCreate,
  DatabaseConnectionUpdate,
} from '../../services/api'

const databaseStore = useDatabaseStore()

const showCreateDialog = ref(false)
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
