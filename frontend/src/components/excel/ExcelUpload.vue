<template>
  <div class="excel-upload">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>Upload Excel File</span>
          <DatabaseSelector />
        </div>
      </template>

      <el-upload
        class="upload-area"
        drag
        :auto-upload="false"
        :on-change="handleFileChange"
        :show-file-list="false"
        accept=".xls,.xlsx"
      >
        <el-icon class="upload-icon"><UploadFilled /></el-icon>
        <div class="upload-text">
          <p>Drop Excel file here or <em>click to upload</em></p>
          <p class="hint">Support .xls and .xlsx files (max {{ maxSize }}MB)</p>
        </div>
      </el-upload>

      <div v-if="selectedFile" class="selected-file">
        <el-icon><Document /></el-icon>
        <span>{{ selectedFile.name }}</span>
        <span class="file-size">({{ formatFileSize(selectedFile.size) }})</span>
        <el-button size="small" type="danger" @click="clearFile">
          <el-icon><Delete /></el-icon>
        </el-button>
      </div>

      <!-- Named after the file; the user may rename it, and must when the
           name is already taken. -->
      <div v-if="selectedFile" class="table-name">
        <label class="tn-label">테이블 이름</label>
        <el-input
          v-model="tableName"
          size="default"
          placeholder="만들 테이블 이름"
          style="width: 360px"
          :class="{ taken: nameCheck && !nameCheck.available }"
          @input="scheduleCheck"
        >
          <template #prepend>kfms_upload.</template>
        </el-input>
        <div class="tn-status">
          <span v-if="checking" class="muted">확인 중…</span>
          <template v-else-if="nameCheck">
            <span v-if="!nameCheck.available" class="bad">
              '{{ nameCheck.conflict_with }}' 테이블이 이미 있습니다 — 다른 이름을 입력하세요
            </span>
            <span v-else class="good">
              사용할 수 있습니다
              <template v-if="nameCheck.name !== tableName.trim()">
                · 실제 이름: <code>{{ nameCheck.key }}</code>
              </template>
            </span>
          </template>
        </div>
      </div>

      <div class="upload-actions">
        <el-button
          type="primary"
          @click="uploadFile"
          :loading="uploading"
          :disabled="!selectedFile || !databaseStore.activeConnectionId || !canUpload"
        >
          <el-icon><Upload /></el-icon>
          Upload & Create Table
        </el-button>

        <el-alert
          v-if="!databaseStore.activeConnectionId"
          type="warning"
          :closable="false"
          show-icon
        >
          <template #title>
            Please select a database first
          </template>
        </el-alert>
      </div>

      <!-- Uploaded Files List -->
      <div v-if="uploads.length > 0" class="uploads-list">
        <h4>Uploaded Excel Files</h4>
        <el-table :data="uploads" stripe>
          <el-table-column prop="filename" label="Filename" />
          <el-table-column prop="table_name" label="Table Name" />
          <el-table-column label="Rows">
            <template #default="{ row }">{{ row.row_count.toLocaleString() }}</template>
          </el-table-column>
          <el-table-column label="Expires">
            <template #default="{ row }">{{ formatExpiry(row.expires_at) }}</template>
          </el-table-column>
          <el-table-column label="Actions" width="230">
            <template #default="{ row }">
              <el-button size="small" title="만료를 24시간 늘립니다" @click="extendUpload(row.id)">
                연장
              </el-button>
              <el-button size="small" @click="queryTable(row.table_name)">
                <el-icon><Search /></el-icon>
                Query
              </el-button>
              <el-popconfirm
                title="Delete this upload?"
                @confirm="deleteUpload(row.id)"
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
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useRouter } from 'vue-router'
import { UploadFilled, Document, Delete, Upload, Search } from '@element-plus/icons-vue'
import type { UploadFile } from 'element-plus'
import { ElMessage } from 'element-plus'
import { api } from '../../services/api'
import { useDatabaseStore } from '../../stores/database'
import DatabaseSelector from '../database/DatabaseSelector.vue'

const router = useRouter()
const databaseStore = useDatabaseStore()

const selectedFile = ref<File | null>(null)
const tableName = ref('')
const nameCheck = ref<Awaited<ReturnType<typeof api.excel.checkTableName>> | null>(null)
const checking = ref(false)
let checkTimer: ReturnType<typeof setTimeout> | undefined
let checkSeq = 0

const canUpload = computed(
  () => !!tableName.value.trim() && !checking.value && !!nameCheck.value?.available
)

/** Ask the server what the name becomes and whether it is free. Only the
 *  latest answer counts, so quick typing cannot show a stale result. */
async function checkName() {
  const id = databaseStore.activeConnectionId
  const name = tableName.value.trim()
  if (!id || !name) {
    nameCheck.value = null
    return
  }
  const seq = ++checkSeq
  checking.value = true
  try {
    const result = await api.excel.checkTableName(id, name)
    if (seq === checkSeq) nameCheck.value = result
  } catch {
    if (seq === checkSeq) nameCheck.value = null
  } finally {
    if (seq === checkSeq) checking.value = false
  }
}

function scheduleCheck() {
  clearTimeout(checkTimer)
  checking.value = true
  checkTimer = setTimeout(checkName, 300)
}

// Another target database may already hold the name, or not.
watch(() => databaseStore.activeConnectionId, () => {
  if (selectedFile.value) checkName()
})
const uploading = ref(false)
const uploads = ref<any[]>([])
const maxSize = 50 // MB

function handleFileChange(file: UploadFile) {
  if (file.raw) {
    selectedFile.value = file.raw
    // Start from the file name; the server turns it into a valid table name.
    tableName.value = file.raw.name.replace(/\.(xlsx|xls)$/i, '')
    checkName().then(() => {
      if (nameCheck.value) tableName.value = nameCheck.value.name
    })
  }
}

function clearFile() {
  selectedFile.value = null
  tableName.value = ''
  nameCheck.value = null
}

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return bytes + ' B'
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB'
  return (bytes / (1024 * 1024)).toFixed(1) + ' MB'
}

function formatExpiry(expiresAt: string): string {
  const date = new Date(expiresAt)
  const now = new Date()
  const diffMs = date.getTime() - now.getTime()
  const diffHrs = Math.round(diffMs / (1000 * 60 * 60))

  if (diffHrs < 0) return 'Expired — 곧 자동 삭제'
  if (diffHrs < 1) return 'Less than 1 hour'
  if (diffHrs === 1) return '1 hour'
  return `${diffHrs} hours`
}

async function uploadFile() {
  if (!selectedFile.value || !databaseStore.activeConnectionId) return

  uploading.value = true

  try {
    const result = await api.excel.upload(
      selectedFile.value,
      databaseStore.activeConnectionId,
      undefined,
      tableName.value.trim()
    )

    ElMessage.success({
      message: `Excel uploaded! Table "${result.table_name}" created with ${result.row_count} rows.`,
      duration: 5000
    })

    clearFile()
    await fetchUploads()
    // The new table must show in the query tree without a page reload.
    await refreshTables(databaseStore.activeConnectionId)
  } catch (error: any) {
    const message = error.response?.data?.detail || 'Upload failed'
    ElMessage.error(message)
    // Taken since the last check: show it next to the name field too.
    if (error.response?.status === 409) await checkName()
  } finally {
    uploading.value = false
  }
}

/** Re-read the table list; a failure here must not undo a finished upload. */
async function refreshTables(connectionId: number | null) {
  if (!connectionId) return
  try {
    await databaseStore.refreshSchema(connectionId)
  } catch {
    // The tree offers its own retry.
  }
}

async function fetchUploads() {
  try {
    uploads.value = await api.excel.list()
  } catch (error) {
    console.error('Failed to fetch uploads:', error)
  }
}

async function extendUpload(uploadId: number) {
  try {
    await api.excel.extend(uploadId, 24)
    ElMessage.success('만료를 24시간 늘렸습니다')
    await fetchUploads()
  } catch (error: any) {
    ElMessage.error(error.response?.data?.detail || '연장하지 못했습니다')
  }
}

async function deleteUpload(uploadId: number) {
  if (!databaseStore.activeConnectionId) return

  try {
    await api.excel.delete(uploadId, databaseStore.activeConnectionId)
    ElMessage.success('Upload deleted')
    await fetchUploads()
    await refreshTables(databaseStore.activeConnectionId)
  } catch (error: any) {
    ElMessage.error('Failed to delete upload')
  }
}

function queryTable(tableName: string) {
  router.push({
    path: '/query',
    query: { table: tableName }
  })
}

onMounted(() => {
  if (databaseStore.connections.length === 0) {
    databaseStore.fetchConnections(true)
  }
  fetchUploads()
})
</script>

<style scoped>
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.upload-area {
  margin-bottom: 20px;
}

.upload-icon {
  font-size: 67px;
  color: #409eff;
  margin-bottom: 16px;
}

.upload-text {
  text-align: center;
}

.upload-text p {
  margin: 5px 0;
}

.hint {
  font-size: 12px;
  color: #909399;
}

.selected-file {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 15px;
  background: #f0f9ff;
  border-radius: 4px;
  margin-bottom: 20px;
}

.file-size {
  color: #909399;
  font-size: 13px;
}

.table-name {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 10px;
  margin-bottom: 16px;
}

.tn-label {
  font-size: 13px;
  font-weight: 600;
  color: #344054;
}

.tn-status {
  font-size: 12.5px;
}

.tn-status .good {
  color: #067647;
}

.tn-status .bad {
  color: #b42318;
}

.tn-status .muted {
  color: #8a94a3;
}

.taken :deep(.el-input__wrapper) {
  box-shadow: 0 0 0 1px #f04438 inset;
}

.upload-actions {
  display: flex;
  flex-direction: column;
  gap: 15px;
}

.uploads-list {
  margin-top: 30px;
  padding-top: 30px;
  border-top: 1px solid #ebeef5;
}

.uploads-list h4 {
  margin: 0 0 15px 0;
  color: #303133;
}
</style>
