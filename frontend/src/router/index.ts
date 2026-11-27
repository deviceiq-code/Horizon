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
        // Account managers became users with the "Account Manager" role
        ...['account-managers', 'admin/account-managers'].map((path) => ({
          path,
          redirect: { name: 'users', query: { role: 'account_manager' } },
        })),
        {
          path: 'settings',
          name: 'settings',
          component: () => import('@/views/SettingsView.vue'),
          meta: { titleKey: 'menu.settings' },
          // The former system settings: photo search is each user's Smart Tool now
          beforeEnter: (to) =>
            to.query.tab === 'system'
              ? { name: 'settings', query: { tab: 'smartTools' } }
              : undefined,
        },
        {
          // One search over every module (src/search.ts; side menu › Pages; Ctrl+K)
          path: 'search',
          name: 'search',
          component: () => import('@/views/SearchView.vue'),
          meta: { titleKey: 'menu.search' },
        },
        {
          // The user's own notifications (the top bar's bell; side menu › Pages)
          path: 'notifications',
          name: 'notifications',
          component: () => import('@/views/NotificationsView.vue'),
          meta: { titleKey: 'menu.notifications' },
        },
        {
          path: 'admin/system-settings',
          redirect: { name: 'settings', query: { tab: 'smartTools' } },
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
