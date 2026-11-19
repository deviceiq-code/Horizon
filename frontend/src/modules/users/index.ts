import type { AppModule } from '@/modules'

/** Users of the system and their roles (administrators only). */
const users: AppModule = {
  name: 'users',
  icon: 'mdi-account-group-outline',
  titleKey: 'users.title',
  placement: 'system',
  adminOnly: true,
  routes: [
    {
      path: 'users',
      name: 'users',
      component: () => import('./UsersView.vue'),
    },
  ],
}

export default users
