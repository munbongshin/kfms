<template>
  <div class="login-page">
    <form class="card" @submit.prevent="submit">
      <LanguageSwitch class="light lang" />
      <div class="brand">KFMS</div>
      <div class="sub">Knowledge Flow Management System</div>

      <template v-if="auth.setupRequired">
        <h2>{{ $t('관리자 계정 만들기') }}</h2>
        <p class="hint">{{ $t('처음 실행입니다. 모든 설정과 사용자를 관리할 관리자 계정을 먼저 만드세요.') }}</p>
      </template>
      <h2 v-else>{{ $t('로그인') }}</h2>

      <label>{{ $t('아이디') }}</label>
      <el-input v-model="username" autocomplete="username" :placeholder="$t('아이디')" size="large" autofocus />

      <template v-if="auth.setupRequired">
        <label>{{ $t('이름') }} <small>{{ $t('(선택)') }}</small></label>
        <el-input v-model="displayName" :placeholder="$t('표시할 이름')" size="large" />
      </template>

      <label>{{ $t('비밀번호') }} <small v-if="auth.setupRequired">{{ $t('(8자 이상)') }}</small></label>
      <el-input
        v-model="password"
        type="password"
        show-password
        :autocomplete="auth.setupRequired ? 'new-password' : 'current-password'"
        :placeholder="$t('비밀번호')"
        size="large"
      />

      <template v-if="auth.setupRequired">
        <label>{{ $t('비밀번호 확인') }}</label>
        <el-input v-model="confirm" type="password" show-password autocomplete="new-password" size="large" />
      </template>

      <div v-if="error" class="error">{{ error }}</div>

      <button class="submit" type="submit" :disabled="busy || !canSubmit">
        {{ busy ? $t('처리 중…') : auth.setupRequired ? $t('관리자 계정 만들기') : $t('로그인') }}
      </button>
    </form>
  </div>
</template>

<script setup lang="ts">
import { t } from '../i18n'
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import LanguageSwitch from '../components/layout/LanguageSwitch.vue'

const auth = useAuthStore()
const router = useRouter()

const username = ref('')
const displayName = ref('')
const password = ref('')
const confirm = ref('')
const busy = ref(false)
const error = ref('')

const canSubmit = computed(() => {
  if (!username.value.trim() || !password.value) return false
  return auth.setupRequired ? password.value.length >= 8 && password.value === confirm.value : true
})

async function submit() {
  if (!canSubmit.value) return
  busy.value = true
  error.value = ''
  try {
    if (auth.setupRequired) {
      await auth.setup({
        username: username.value.trim(),
        display_name: displayName.value.trim(),
        password: password.value,
      })
    } else {
      await auth.login(username.value.trim(), password.value)
    }
    router.replace({ name: 'query' })
  } catch (e: any) {
    const detail = e.response?.data?.detail
    error.value = typeof detail === 'string' ? detail : t('처리하지 못했습니다. 입력을 확인하세요.')
  } finally {
    busy.value = false
  }
}
</script>

<style scoped>
.login-page {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #1b3c74;
}

.card {
  position: relative;
  width: 380px;
  padding: 32px 34px 30px;
  background: #fff;
  border-radius: 4px;
  box-shadow: 0 10px 30px rgba(0, 0, 0, 0.25);
}

.lang {
  position: absolute;
  top: 14px;
  right: 16px;
}

.brand {
  font-size: 26px;
  font-weight: 800;
  letter-spacing: 1px;
  color: #1b3c74;
}

.sub {
  margin-bottom: 18px;
  font-size: 12px;
  color: #8a94a3;
}

h2 {
  margin: 0 0 6px;
  font-size: 17px;
  color: #1f3a66;
}

.hint {
  margin: 0 0 8px;
  font-size: 12.5px;
  line-height: 1.6;
  color: #6b7686;
}

label {
  display: block;
  margin: 14px 0 5px;
  font-size: 13px;
  font-weight: 600;
  color: #344054;
}

label small {
  font-weight: 400;
  color: #8a94a3;
}

.error {
  margin-top: 14px;
  padding: 8px 10px;
  background: #fef3f2;
  border-left: 3px solid #f04438;
  font-size: 13px;
  color: #b42318;
}

.submit {
  width: 100%;
  height: 42px;
  margin-top: 20px;
  border: none;
  background: #1a5fa8;
  color: #fff;
  font-size: 15px;
  font-weight: 600;
  cursor: pointer;
}

.submit:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
</style>
