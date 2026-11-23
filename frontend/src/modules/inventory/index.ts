/**
 * Remarketing › Inventory: appointments (receivings and shipments), receiving lots (triage),
 * the scan-driven movement page and the inventory's pages (assets, accessories, locations,
 * containers, labels). Warehouses live in their own folder.
 */
import { defineAsyncComponent, type Component } from 'vue'
import { RouterView } from 'vue-router'
import type { AppModule } from '@/modules'

export const INVENTORY_SECTION = 'menu.sections.inventory'

function page(
  name: string,
  path: string,
  icon: string,
  key: string,
  view: () => Promise<{ default: Component }>,
  catalogPage = true,
): AppModule {
  return {
    name,
    icon,
    titleKey: `${key}.title`,
    app: 'remarketing',
    section: INVENTORY_SECTION,
    routes: [
      catalogPage
        ? {
            path: `inventory/${path}`,
            name,
            component: () => import('@/modules/catalogs/CatalogPage.vue'),
            props: {
              titleKey: `${key}.title`,
              subtitleKey: `${key}.subtitle`,
              view: defineAsyncComponent(view),
            },
          }
        : { path: `inventory/${path}`, name, component: view },
    ],
  }
}

export const appointments = page(
  'inventory-appointments',
  'appointments',
  'mdi-calendar-clock',
  'inventory.appointments',
  () => import('./AppointmentsView.vue'),
  false,
)

export const receiving: AppModule = {
  name: 'inventory-receiving',
  icon: 'mdi-truck-check-outline',
  titleKey: 'inventory.lots.title',
  app: 'remarketing',
  section: INVENTORY_SECTION,
  routes: [
    {
      // The menu links here; the list of lots and a lot are its pages
      path: 'inventory/receiving',
      name: 'inventory-receiving',
      component: RouterView,
      redirect: { name: 'inventory-lots' },
      children: [
        { path: '', name: 'inventory-lots', component: () => import('./ReceivingView.vue') },
        {
          path: ':id(\\d+)',
          name: 'inventory-lot',
          meta: { titleKey: 'inventory.lots.lot' },
          component: () => import('./LotView.vue'),
          props: (route) => ({ id: Number(route.params.id) }),
        },
      ],
    },
  ],
}

export const movement = page(
  'inventory-movement',
  'movement',
  'mdi-barcode-scan',
  'inventory.movement',
  () => import('./MovementView.vue'),
  false,
)

export const assets = page(
  'inventory-assets',
  'assets',
  'mdi-package-variant-closed',
  'inventory.assets',
  () => import('./AssetsTab.vue'),
)

export const accessories = page(
  'inventory-accessories',
  'accessories',
  'mdi-counter',
  'inventory.accessories',
  () => import('./AccessoriesTab.vue'),
)

export const locations = page(
  'inventory-locations',
  'locations',
  'mdi-file-tree-outline',
  'inventory.locations',
  () => import('./LocationsTab.vue'),
)

export const containers = page(
  'inventory-containers',
  'containers',
  'mdi-package-variant',
  'inventory.containers',
  () => import('./ContainersTab.vue'),
)

export const labels = page(
  'inventory-labels',
  'labels',
  'mdi-barcode',
  'inventory.labels',
  () => import('./LabelsTab.vue'),
)

// Inventory opens its first page
appointments.routes.push({ path: 'inventory', redirect: { name: 'inventory-appointments' } })

export default [
  appointments,
  receiving,
  movement,
  assets,
  accessories,
  locations,
  containers,
  labels,
]
