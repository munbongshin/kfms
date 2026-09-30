import { createRouter, createWebHistory, RouteRecordRaw } from 'vue-router'
import { t } from '../i18n'
import { useAuthStore } from '../stores/auth'

const routes: Array<RouteRecordRaw> = [
  {
    path: '/',
    redirect: '/query'
  },
  {
    path: '/query',
    name: 'query',
    component: () => import('../views/QueryView.vue'),
    meta: { title: '질의' }
  },
  {
    path: '/databases',
    name: 'databases',
    component: () => import('../views/DatabaseView.vue'),
    meta: { title: '데이터', roles: ['admin'] }
  },
  {
    path: '/history',
    name: 'history',
    component: () => import('../views/HistoryView.vue'),
    meta: { title: '이력' }
  }
  ,{
    path: '/reports',
    name: 'reports',
    component: () => import('../views/ReportsView.vue'),
    meta: { title: '보고서' }
  }
  ,{
    path: '/anomaly',
    name: 'anomaly',
    component: () => import('../views/AnomalyView.vue'),
    meta: { title: '점검', roles: ['admin', 'auditor'] }
  }
  ,{
    path: '/settings',
    name: 'settings',
    component: () => import('../views/SettingsView.vue'),
    meta: { title: '설정', roles: ['admin'] }
  }
  ,{
    path: '/admin',
    name: 'admin',
    component: () => import('../views/AdminView.vue'),
    meta: { title: '관리', roles: ['admin'] }
  }
  ,{
    path: '/login',
    name: 'login',
    component: () => import('../views/LoginView.vue'),
    meta: { title: '로그인', public: true }
  }
  ,{
    path: '/help',
    name: 'help',
    component: () => import('../views/HelpView.vue'),
    meta: { title: '도움말' }
  }
]

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes
})

router.beforeEach(async (to) => {
  document.title = `${to.meta.title ? t(String(to.meta.title)) : 'KFMS'} - Knowledge Flow Management System`

  const auth = useAuthStore()
  try {
    if (!auth.statusLoaded) await auth.checkStatus()
  } catch {
    // The server is down: let the page show its own error rather than loop.
    return true
  }

  // No administrator yet, or nobody signed in: only the sign-in screen.
  if (auth.setupRequired || !auth.token) return to.name === 'login' ? true : { name: 'login' }

  if (!auth.user) await auth.restore()
  if (!auth.user) return { name: 'login' }

  if (to.name === 'login') return { name: 'query' }

  const roles = to.meta.roles as string[] | undefined
  if (roles && !roles.includes(auth.user.role)) return { name: 'query' }
  return true
})

export default router
