import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: '/login',
      name: 'login',
      component: () => import('@/views/LoginView.vue'),
      meta: { publico: true },
    },
    {
      path: '/',
      name: 'home',
      component: () => import('@/views/HomeView.vue'),
    },
  ],
})

router.beforeEach(async (to) => {
  const auth = useAuthStore()
  await auth.carregar()
  if (!to.meta.publico && !auth.autenticado) {
    return { name: 'login', query: { next: to.fullPath } }
  }
  if (to.name === 'login' && auth.autenticado) {
    return { name: 'home' }
  }
})

export default router
