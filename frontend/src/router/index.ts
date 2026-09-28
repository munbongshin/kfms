import { createRouter, createWebHistory, RouteRecordRaw } from 'vue-router'

const routes: Array<RouteRecordRaw> = [
  {
    path: '/',
    redirect: '/query'
  },
  {
    path: '/query',
    name: 'query',
    component: () => import('../views/QueryView.vue'),
    meta: { title: 'Query' }
  },
  {
    path: '/databases',
    name: 'databases',
    component: () => import('../views/DatabaseView.vue'),
    meta: { title: 'Databases' }
  },
  {
    path: '/history',
    name: 'history',
    component: () => import('../views/HistoryView.vue'),
    meta: { title: 'History' }
  }
  ,{
    path: '/anomaly',
    name: 'anomaly',
    component: () => import('../views/AnomalyView.vue'),
    meta: { title: 'Anomaly' }
  }
  ,{
    path: '/settings',
    name: 'settings',
    component: () => import('../views/SettingsView.vue'),
    meta: { title: 'LLM 설정' }
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

router.beforeEach((to, _from, next) => {
  document.title = `${to.meta.title || 'KFMS'} - Knowledge Flow Management System`
  next()
})

export default router
