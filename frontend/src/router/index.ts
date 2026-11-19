import { createRouter, createWebHistory } from 'vue-router'
import { MODULES } from '@/modules'
import { useAuthStore } from '@/stores/auth'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: '/login',
      name: 'login',
      component: () => import('@/views/LoginView.vue'),
      meta: { public: true },
    },
    {
      // Authenticated pages share the top bar and the side menu
      path: '/',
      component: () => import('@/layouts/MainLayout.vue'),
      children: [
        {
          path: '',
          name: 'home',
          component: () => import('@/views/HomeView.vue'),
        },
        // Routes of admin-only modules are marked so the guard below can check them
        ...MODULES.flatMap((module) =>
          module.adminOnly
            ? module.routes.map((route) => ({
                ...route,
                meta: { ...route.meta, adminOnly: true },
              }))
            : module.routes,
        ),
        {
          path: 'settings',
          name: 'settings',
          component: () => import('@/views/SettingsView.vue'),
        },
      ],
    },
  ],
})

router.beforeEach(async (to) => {
  const auth = useAuthStore()
  await auth.load()
  if (!to.meta.public && !auth.isAuthenticated) {
    return { name: 'login', query: { next: to.fullPath } }
  }
  if (to.name === 'login' && auth.isAuthenticated) {
    return { name: 'home' }
  }
  if (to.matched.some((record) => record.meta.adminOnly) && !auth.user?.is_admin) {
    return { name: 'home' }
  }
})

export default router
