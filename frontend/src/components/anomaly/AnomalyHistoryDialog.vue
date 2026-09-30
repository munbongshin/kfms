<template>
  <el-dialog
    :model-value="modelValue"
    title="점검 기준 변경 이력"
    width="680px"
    append-to-body
    @update:model-value="emit('update:modelValue', $event)"
    @open="load"
  >
    <p class="intro">
      누가 언제 어떤 기준을 바꿨는지 최근 순으로 보여 줍니다.
      <template v-if="auth.isAuditor"><em>이 변경 이전으로</em>를 누르면 그 변경을 하기 전의 값으로 되돌립니다. 되돌리는 것도 새 변경으로 남습니다.</template>
    </p>

    <el-empty v-if="!loading && !entries.length" description="아직 바꾼 기록이 없습니다" :image-size="60" />

    <div v-loading="loading" class="list">
      <article v-for="e in entries" :key="e.id" class="entry">
        <header>
          <span class="when">{{ fmt(e.changed_at) }}</span>
          <span class="who">{{ e.changed_by || '알 수 없음' }}</span>
          <span class="spacer" />
          <el-popconfirm
            v-if="auth.isAuditor"
            title="이 변경을 하기 전의 값으로 되돌릴까요?"
            confirm-button-text="되돌리기"
            cancel-button-text="취소"
            @confirm="restore(e)"
          >
            <template #reference>
              <button class="link" :disabled="busy === e.id">{{ busy === e.id ? '되돌리는 중…' : '이 변경 이전으로' }}</button>
            </template>
          </el-popconfirm>
        </header>
        <ul>
          <li v-for="(c, i) in e.changes" :key="i">
            <b>{{ c.rule }}</b> · {{ c.label }}
            <span class="text">{{ c.text }}</span>
          </li>
        </ul>
      </article>
    </div>

    <template #footer>
      <el-button @click="emit('update:modelValue', false)">닫기</el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { ElMessage } from 'element-plus'
import { api, type AnomalySettingHistory } from '../../services/api'
import { useAuthStore } from '../../stores/auth'

defineProps<{ modelValue: boolean }>()
const emit = defineEmits<{ 'update:modelValue': [value: boolean]; restored: [] }>()

const auth = useAuthStore()
const entries = ref<AnomalySettingHistory[]>([])
const loading = ref(false)
const busy = ref<number | null>(null)

const fmt = (iso: string) => new Date(iso).toLocaleString('ko-KR')

async function load() {
  loading.value = true
  try {
    entries.value = await api.anomaly.settingsHistory()
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || '변경 이력을 불러오지 못했습니다')
  } finally {
    loading.value = false
  }
}

async function restore(entry: AnomalySettingHistory) {
  busy.value = entry.id
  try {
    await api.anomaly.restoreSettings(entry.id)
    ElMessage.success('이전 값으로 되돌렸습니다. 다음 조회부터 적용됩니다.')
    await load()
    emit('restored')
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || '되돌리지 못했습니다')
  } finally {
    busy.value = null
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

.list {
  max-height: 420px;
  overflow-y: auto;
}

.entry {
  margin-bottom: 10px;
  padding: 8px 12px;
  border: 1px solid #d3dae3;
  background: #f9fbfd;
}

header {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 13px;
}

.when {
  font-weight: 700;
  color: #1b3c74;
}

.who {
  color: #667085;
}

.spacer {
  flex: 1;
}

ul {
  margin: 6px 0 0;
  padding-left: 18px;
  font-size: 13px;
  line-height: 1.7;
}

.text {
  margin-left: 6px;
  color: #b54708;
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

.link:disabled {
  opacity: 0.5;
  cursor: default;
}
</style>
