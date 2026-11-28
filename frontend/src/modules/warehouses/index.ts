import { defineAsyncComponent } from 'vue'
import type { AppModule } from '@/modules'

/** Asset Management › Inventory › Warehouses: a page like the catalogs' (title, subtitle, grid). */
const warehouses: AppModule = {
  name: 'warehouses',
  icon: 'mdi-warehouse',
  titleKey: 'warehouses.title',
  app: 'assets',
  section: 'menu.sections.inventory',
  routes: [
    {
      path: 'inventory/warehouses',
      name: 'warehouses',
      component: () => import('@/modules/catalogs/CatalogPage.vue'),
      props: {
        titleKey: 'warehouses.title',
        subtitleKey: 'warehouses.subtitle',
        view: defineAsyncComponent(() => import('./WarehousesTab.vue')),
      },
    },
  ],
}

export default warehouses
