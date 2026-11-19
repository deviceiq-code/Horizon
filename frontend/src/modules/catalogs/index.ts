import type { AppModule } from '@/modules'

import { CATALOG_TABS } from './tabs'

const catalogs: AppModule = {
  name: 'catalogs',
  icon: 'mdi-database-cog-outline',
  titleKey: 'catalogs.title',
  placement: 'system',
  routes: [
    {
      // The menu links here; it opens the first tab and stays highlighted on every tab
      path: 'catalogs',
      name: 'catalogs',
      component: () => import('./CatalogsView.vue'),
      redirect: { name: CATALOG_TABS[0]!.name },
      children: [
        {
          path: 'verticals',
          name: 'catalogs-verticals',
          component: () => import('./verticals/VerticalsTab.vue'),
        },
        {
          path: 'asset-classes',
          name: 'catalogs-asset-classes',
          component: () => import('./asset-classes/AssetClassesTab.vue'),
        },
        {
          path: 'manufacturers',
          name: 'catalogs-manufacturers',
          component: () => import('./manufacturers/ManufacturersTab.vue'),
        },
      ],
    },
  ],
}

export default catalogs
