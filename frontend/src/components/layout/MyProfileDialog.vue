<template>
  <el-dialog
    :model-value="modelValue"
    :title="$t('내 정보')"
    width="440px"
    @update:model-value="emit('update:modelValue', $event)"
    @open="reset"
  >
    <div class="fixed">
      <span>{{ $t('아이디') }}</span><b>{{ auth.user?.username }}</b>
      <span>{{ $t('역할') }}</span><b>{{ roleLabel }}</b>
    </div>
    <p class="hint">{{ $t('아이디와 역할은 관리자만 바꿀 수 있습니다.') }}</p>

    <div class="row">
      <label>{{ $t('이름') }}</label>
      <el-input v-model="displayName" maxlength="100" :placeholder="$t('화면에 표시할 이름')" />
    </div>

    <div class="section">{{ $t('비밀번호 바꾸기') }} <small>{{ $t('(바꿀 때만 입력)') }}</small></div>
    <div class="row">
      <label>{{ $t('현재 비밀번호') }}</label>
      <el-input v-model="current" type="password" show-password autocomplete="current-password" />
    </div>
    <div class="row">
      <label>{{ $t('새 비밀번호') }}</label>
      <el-input v-model="next" type="password" show-password autocomplete="new-password" :placeholder="$t('8자 이상')" />
    </div>
    <div class="row">
      <label>{{ $t('새 비밀번호 확인') }}</label>
      <el-input v-model="confirm" type="password" show-password autocomplete="new-password" />
    </div>
    <div v-if="mismatch" class="error">{{ $t('새 비밀번호가 서로 다릅니다') }}</div>
    <div v-if="error" class="error">{{ error }}</div>

    <template #footer>
      <el-button @click="emit('update:modelValue', false)">{{ $t('취소') }}</el-button>
      <el-button type="primary" :loading="saving" :disabled="!canSave" @click="save">{{ $t('저장') }}</el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { roleName, t } from '../../i18n'
import { computed, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { useAuthStore } from '../../stores/auth'

defineProps<{ modelValue: boolean }>()
const emit = defineEmits<{ 'update:modelValue': [value: boolean] }>()

const auth = useAuthStore()
const roleLabel = computed(() => roleName(auth.role))

const displayName = ref('')
const current = ref('')
const next = ref('')
const confirm = ref('')
const saving = ref(false)
const error = ref('')

const changingPassword = computed(() => !!(current.value || next.value || confirm.value))
const mismatch = computed(() => !!confirm.value && next.value !== confirm.value)
const nameChanged = computed(() => displayName.value.trim() !== (auth.user?.display_name || ''))

const canSave = computed(() => {
  if (changingPassword.value) {
    return !!current.value && next.value.length >= 8 && next.value === confirm.value
  }
  return nameChanged.value
})

function reset() {
  displayName.value = auth.user?.display_name || ''
  current.value = next.value = confirm.value = ''
  error.value = ''
}

async function save() {
  saving.value = true
  error.value = ''
  try {
    await auth.updateProfile({
      display_name: nameChanged.value ? displayName.value.trim() : undefined,
      current_password: changingPassword.value ? current.value : undefined,
      new_password: changingPassword.value ? next.value : undefined,
    })
    ElMessage.success(t('내 정보를 저장했습니다'))
    emit('update:modelValue', false)
  } catch (e: any) {
    const detail = e.response?.data?.detail
    error.value = typeof detail === 'string' ? detail : t('저장하지 못했습니다. 입력을 확인하세요.')
  } finally {
    saving.value = false
  }
}
</script>

<style scoped>
.fixed {
  display: grid;
  grid-template-columns: 70px 1fr;
  gap: 6px 10px;
  padding: 10px 12px;
  background: #f7f9fc;
  border: 1px solid #d3dae3;
  font-size: 13px;
}

.fixed span {
  color: #6b7686;
}

.hint {
  margin: 6px 0 14px;
  font-size: 12px;
  color: #8a94a3;
}

.section {
  margin: 16px 0 8px;
  font-size: 13px;
  font-weight: 700;
  color: #1f3a66;
}

.section small {
  font-weight: 400;
  color: #8a94a3;
}

.row {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 10px;
}

.row label {
  flex: 0 0 110px;
  font-size: 13px;
  font-weight: 600;
  color: #344054;
}

.error {
  margin-top: 6px;
  padding: 7px 10px;
  background: #fef3f2;
  border-left: 3px solid #f04438;
  font-size: 12.5px;
  color: #b42318;
}
</style>
