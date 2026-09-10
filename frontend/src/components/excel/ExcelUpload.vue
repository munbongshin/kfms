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

      <div class="upload-actions">
        <el-button
          type="primary"
          @click="uploadFile"
          :loading="uploading"
          :disabled="!selectedFile || !databaseStore.activeConnectionId"
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
          <el-table-column label="Actions" width="150">
            <template #default="{ row }">
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
import { ref, onMounted } from 'vue'
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
const uploading = ref(false)
const uploads = ref<any[]>([])
const maxSize = 50 // MB

function handleFileChange(file: UploadFile) {
  if (file.raw) {
    selectedFile.value = file.raw
  }
}

function clearFile() {
  selectedFile.value = null
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

  if (diffHrs < 0) return 'Expired'
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
      databaseStore.activeConnectionId
    )

    ElMessage.success({
      message: `Excel uploaded! Table "${result.table_name}" created with ${result.row_count} rows.`,
      duration: 5000
    })

    clearFile()
    await fetchUploads()
  } catch (error: any) {
    const message = error.response?.data?.detail || 'Upload failed'
    ElMessage.error(message)
  } finally {
    uploading.value = false
  }
}

async function fetchUploads() {
  try {
    uploads.value = await api.excel.list()
  } catch (error) {
    console.error('Failed to fetch uploads:', error)
  }
}

async function deleteUpload(uploadId: number) {
  if (!databaseStore.activeConnectionId) return

  try {
    await api.excel.delete(uploadId, databaseStore.activeConnectionId)
    ElMessage.success('Upload deleted')
    await fetchUploads()
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
