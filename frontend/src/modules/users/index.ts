import type { AppModule } from '@/modules'

export const MANAGEMENT_SECTION = 'menu.sections.management'

/** Users of the system (administrators only). */
export const users: AppModule = {
  name: 'users',
  icon: 'mdi-account-group-outline',
  titleKey: 'users.title',
  app: 'admin',
  section: MANAGEMENT_SECTION,
  adminOnly: true,
  routes: [
    {
      path: 'users',
      name: 'users',
      component: () => import('./UsersView.vue'),
      // The former Roles tab (?tab=roles) is a page of its own now
      beforeEnter: (to) =>
        to.query.tab === 'roles' ? { name: 'roles', query: {}, replace: true } : true,
    },
  ],
}

/** Roles of the users (administrators only). */
export const roles: AppModule = {
  name: 'roles',
  icon: 'mdi-shield-account-outline',
  titleKey: 'users.tabs.roles',
  app: 'admin',
  section: MANAGEMENT_SECTION,
  adminOnly: true,
  routes: [{ path: 'roles', name: 'roles', component: () => import('./RolesView.vue') }],
}

export default users
