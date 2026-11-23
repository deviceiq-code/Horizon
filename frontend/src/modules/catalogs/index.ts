/**
 * Small reference tables ("Catalogs"), shared by every app. Each one is a module of
 * Administration in the side menu's "Catalogs" section, with its own page (CatalogPage.vue).
 * To add one: its folder (api.ts, <Name>Tab.vue — a ServerCrudTable with column filters, as
 * Asset Classes' —, form dialog), an entry here and in MODULES (src/modules/index.ts). Customers
 * and service providers are catalogs too, built with `catalog()` in their own folders.
 */
import { defineAsyncComponent, type Component } from 'vue'
import type { AppModule } from '@/modules'

export const CATALOGS_SECTION = 'menu.sections.catalogs'

export function catalog(
  name: string,
  path: string,
  icon: string,
  key: string,
  view: () => Promise<{ default: Component }>,
): AppModule {
  return {
    name,
    icon,
    titleKey: `${key}.title`,
    app: 'admin',
    section: CATALOGS_SECTION,
    routes: [
      {
        path: `catalogs/${path}`,
        name,
        component: () => import('./CatalogPage.vue'),
        props: {
          titleKey: `${key}.title`,
          subtitleKey: `${key}.subtitle`,
          view: defineAsyncComponent(view),
        },
      },
    ],
  }
}

export const verticals = catalog(
  'catalogs-verticals',
  'verticals',
  'mdi-shape-outline',
  'verticals',
  () => import('./verticals/VerticalsTab.vue'),
)
// The former Catalogs page (/admin/catalogs) opens its first table
verticals.routes.push({ path: 'catalogs', name: 'catalogs', redirect: { name: verticals.name } })

export const assetClasses = catalog(
  'catalogs-asset-classes',
  'asset-classes',
  'mdi-tag-multiple-outline',
  'assetClasses',
  () => import('./asset-classes/AssetClassesTab.vue'),
)

export const manufacturers = catalog(
  'catalogs-manufacturers',
  'manufacturers',
  'mdi-factory',
  'manufacturers',
  () => import('./manufacturers/ManufacturersTab.vue'),
)

export const assetModels = catalog(
  'catalogs-asset-models',
  'asset-models',
  'mdi-shape-plus-outline',
  'assetModels',
  () => import('./asset-models/AssetModelsTab.vue'),
)

export default [verticals, assetClasses, assetModels, manufacturers]
