import type { AppModule } from '@/modules'

const customers: AppModule = {
  name: 'customers',
  icon: 'mdi-domain',
  titleKey: 'customers.title',
  app: 'admin',
  section: 'menu.sections.management',
  routes: [
    {
      path: 'customers',
      name: 'customers',
      component: () => import('./CustomersView.vue'),
    },
  ],
}

export default customers
