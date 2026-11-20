import type { AppModule } from '@/modules'

const accountManagers: AppModule = {
  name: 'account-managers',
  icon: 'mdi-account-tie',
  titleKey: 'accountManagers.title',
  app: 'admin',
  routes: [
    {
      path: 'account-managers',
      name: 'account-managers',
      component: () => import('./AccountManagersView.vue'),
    },
  ],
}

export default accountManagers
