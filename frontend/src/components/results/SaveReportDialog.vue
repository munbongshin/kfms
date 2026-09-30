<template>
  <el-dialog
    :model-value="modelValue"
    title="보고서로 저장"
    width="480px"
    @update:model-value="emit('update:modelValue', $event)"
    @open="reset"
  >
    <p class="intro">이 질문을 정한 시각에 자동으로 실행하고, 최근 결과를 <b>보고서</b> 화면에 보관합니다.</p>

    <div class="row">
      <label>보고서 이름</label>
      <el-input v-model="name" placeholder="예: 주간 고액 결제 현황" maxlength="200" />
    </div>

    <div class="row">
      <label>실행 주기</label>
      <el-select v-model="frequency" style="width: 130px">
        <el-option value="daily" label="매일" />
        <el-option value="weekly" label="매주" />
        <el-option value="monthly" label="매월" />
      </el-select>

      <el-select v-if="frequency === 'weekly'" v-model="weekday" style="width: 110px">
        <el-option v-for="(d, i) in DAYS" :key="i" :value="i" :label="`${d}요일`" />
      </el-select>
      <el-select v-if="frequency === 'monthly'" v-model="day" style="width: 110px">
        <el-option v-for="d in 28" :key="d" :value="d" :label="`${d}일`" />
      </el-select>

      <el-select v-model="hour" style="width: 110px">
        <el-option v-for="h in 24" :key="h" :value="h - 1" :label="`${String(h - 1).padStart(2, '0')}시`" />
      </el-select>
    </div>
    <p class="hint">서버 시각 기준입니다. 29일 이후는 없는 달이 있어 매월은 28일까지만 고를 수 있습니다.</p>

    <template #footer>
      <el-button @click="emit('update:modelValue', false)">취소</el-button>
      <el-button type="primary" :loading="saving" :disabled="!name.trim()" @click="save">저장</el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { ElMessage } from 'element-plus'
import { api } from '../../services/api'
import { useDatabaseStore } from '../../stores/database'

const props = defineProps<{ modelValue: boolean; question: string; sql?: string; historyId?: number }>()
const emit = defineEmits<{ 'update:modelValue': [value: boolean]; saved: [] }>()

const databaseStore = useDatabaseStore()
const DAYS = ['월', '화', '수', '목', '금', '토', '일']

const name = ref('')
const frequency = ref<'daily' | 'weekly' | 'monthly'>('weekly')
const hour = ref(9)
const weekday = ref(0)
const day = ref(1)
const saving = ref(false)

function reset() {
  name.value = props.question.slice(0, 60)
}

async function save() {
  const database = databaseStore.activeConnectionId
  if (!database) return
  saving.value = true
  try {
    await api.reports.create({
      name: name.value.trim(),
      question: props.question,
      // The record is what the server reads the SQL from; only administrators have the text.
      history_id: props.historyId || undefined,
      sql: props.sql || undefined,
      database_id: database,
      frequency: frequency.value,
      hour: hour.value,
      weekday: frequency.value === 'weekly' ? weekday.value : undefined,
      day: frequency.value === 'monthly' ? day.value : undefined,
    })
    ElMessage.success('보고서로 저장했습니다. 보고서 화면에서 확인하세요.')
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
  margin: 0 0 14px;
  font-size: 13px;
  line-height: 1.6;
  color: #475467;
}

.row {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 12px;
}

.row label {
  flex: 0 0 80px;
  font-size: 13px;
  font-weight: 600;
  color: #344054;
}

.hint {
  margin: 0;
  font-size: 12px;
  color: #8a94a3;
}
</style>
