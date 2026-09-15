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
