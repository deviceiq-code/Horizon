/**
 * Small reference tables shown as tabs on the Catalogs page. To add one, create its folder
 * (api.ts, <Name>Tab.vue — usually a ServerCrudTable —, form dialog), add a route in ./index.ts
 * and an entry here.
 */
export interface CatalogTab {
  /** Route name of the tab */
  name: string
  icon: string
  titleKey: string
}

export const CATALOG_TABS: CatalogTab[] = [
  { name: 'catalogs-verticals', icon: 'mdi-shape-outline', titleKey: 'verticals.title' },
  {
    name: 'catalogs-asset-classes',
    icon: 'mdi-tag-multiple-outline',
    titleKey: 'assetClasses.title',
  },
  { name: 'catalogs-manufacturers', icon: 'mdi-factory', titleKey: 'manufacturers.title' },
]
