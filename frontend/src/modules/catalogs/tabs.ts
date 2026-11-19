/**
 * Small reference tables shown as tabs on the Catalogs page. To add one, create its folder
 * (api.ts, <Name>Tab.vue, form dialog), add a route in ./index.ts and an entry here.
 */
export interface CatalogTab {
  /** Route name of the tab */
  name: string
  icon: string
  titleKey: string
}

export const CATALOG_TABS: CatalogTab[] = [
  { name: 'catalogs-verticals', icon: 'mdi-shape-outline', titleKey: 'verticals.title' },
]
