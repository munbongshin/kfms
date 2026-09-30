<template>
  <el-card v-if="bookmarks.length > 0" class="bookmark-bar">
    <template #header>
      <div class="header">
        <span>⭐ 자주 쓰는 질문</span>
        <span class="hint">저장된 질문을 바로 실행합니다</span>
      </div>
    </template>
    <div class="items">
      <el-button
        v-for="bookmark in bookmarks"
        :key="bookmark.id"
        size="small"
        round
        :loading="runningId === bookmark.id"
        :disabled="queryStore.loading"
        @click="run(bookmark)"
      >
        {{ bookmark.question }}
      </el-button>
    </div>
  </el-card>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { api } from '../../services/api'
import { useQueryStore } from '../../stores/query'

const queryStore = useQueryStore()

const bookmarks = ref<any[]>([])
const runningId = ref<number | null>(null)

async function fetchBookmarks() {
  try {
    bookmarks.value = await api.history.list({ bookmarked: true, limit: 20 })
  } catch (error) {
    // Bookmarks are a shortcut, so a failed fetch must not block asking a question.
    bookmarks.value = []
  }
}

async function run(bookmark: any) {
  runningId.value = bookmark.id
  try {
    await queryStore.runSavedSQL(
      bookmark.question,
      bookmark.generated_sql,
      Number(bookmark.database_id),
      bookmark.id
    )
  } finally {
    runningId.value = null
  }
}

onMounted(fetchBookmarks)
</script>

<style scoped>
.header {
  display: flex;
  align-items: baseline;
  gap: 10px;
}

.hint {
  color: #909399;
  font-size: 12px;
}

.items {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.items .el-button {
  margin-left: 0;
  max-width: 100%;
}
</style>
