/**
 * Remarketing › Inventory: the scan-driven movement page and the inventory's pages (assets,
 * locations, containers, labels). Warehouses live in their own folder.
 */
import { defineAsyncComponent, type Component } from 'vue'
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

export const movement = page(
  'inventory-movement',
  'movement',
  'mdi-barcode-scan',
  'inventory.movement',
  () => import('./MovementView.vue'),
  false,
)
// Inventory opens its first page
movement.routes.push({ path: 'inventory', redirect: { name: 'inventory-movement' } })

export const assets = page(
  'inventory-assets',
  'assets',
  'mdi-package-variant-closed',
  'inventory.assets',
  () => import('./AssetsTab.vue'),
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

export default [movement, assets, locations, containers, labels]
