/**
 * Auth Store (Pinia)
 * Who is signed in, and what they may open.
 */
import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import { api, TOKEN_KEY, type AppUser, type NewUser, type Role } from '../services/api'

export const useAuthStore = defineStore('auth', () => {
  const token = ref<string | null>(localStorage.getItem(TOKEN_KEY))
  const user = ref<AppUser | null>(null)
  const setupRequired = ref(false)
  const statusLoaded = ref(false)

  const role = computed<Role | null>(() => user.value?.role ?? null)
  const isAdmin = computed(() => role.value === 'admin')
  /** Auditors and administrators: checks, card numbers in full. */
  const isAuditor = computed(() => role.value === 'admin' || role.value === 'auditor')

  function start(session: { token: string; user: AppUser }) {
    token.value = session.token
    user.value = session.user
    setupRequired.value = false
    localStorage.setItem(TOKEN_KEY, session.token)
  }

  async function checkStatus() {
    setupRequired.value = (await api.auth.status()).setup_required
    statusLoaded.value = true
  }

  async function restore() {
    if (!token.value) return
    try {
      user.value = await api.auth.me()
    } catch {
      logout()
    }
  }

  async function login(username: string, password: string) {
    start(await api.auth.login(username, password))
  }

  async function setup(data: NewUser) {
    start(await api.auth.setup(data))
  }

  function logout() {
    token.value = null
    user.value = null
    localStorage.removeItem(TOKEN_KEY)
  }

  return { token, user, role, isAdmin, isAuditor, setupRequired, statusLoaded, checkStatus, restore, login, setup, logout }
})
