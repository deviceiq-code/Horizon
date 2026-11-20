import { createRouter, createWebHistory } from 'vue-router'
import { moduleRoutes } from '@/modules'
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
        // Every module under its app's prefix ("/pricing/...", "/admin/...")
        ...moduleRoutes(),
        {
          path: 'settings',
          name: 'settings',
          component: () => import('@/views/SettingsView.vue'),
          meta: { titleKey: 'menu.settings' },
          // The system tab became Administration → System Settings
          beforeEnter: (to) =>
            to.query.tab === 'system' ? { name: 'system-settings' } : undefined,
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
