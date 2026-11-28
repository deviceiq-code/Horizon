/**
 * Asset Management › Inventory: appointments (receivings and shipments), receiving lots (triage),
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
    app: 'assets',
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
  app: 'assets',
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

export const inspections: AppModule = {
  name: 'inventory-inspections',
  icon: 'mdi-clipboard-search-outline',
  titleKey: 'inventory.inspections.title',
  app: 'assets',
  section: INVENTORY_SECTION,
  routes: [
    {
      // The menu links here; the queue and a report are its pages
      path: 'inventory/inspection',
      name: 'inventory-inspections',
      component: RouterView,
      redirect: { name: 'inventory-inspection-queue' },
      children: [
        {
          path: '',
          name: 'inventory-inspection-queue',
          component: () => import('./InspectionsView.vue'),
        },
        {
          path: ':id(\\d+)',
          name: 'inventory-report',
          meta: { titleKey: 'inventory.reports.report' },
          component: () => import('./ReportView.vue'),
          props: (route) => ({ id: Number(route.params.id) }),
        },
      ],
    },
  ],
}

export const blocks = page(
  'inventory-blocks',
  'blocks',
  'mdi-lock-clock',
  'inventory.blocks',
  () => import('./BlocksView.vue'),
  false,
)

export const disputes = page(
  'inventory-disputes',
  'disputes',
  'mdi-gavel',
  'inventory.disputes',
  () => import('./DisputesView.vue'),
  false,
)

export const stock = page(
  'inventory-stock',
  'stock',
  'mdi-warehouse',
  'inventory.stock',
  () => import('./StockView.vue'),
  false,
)

export const disposals: AppModule = {
  name: 'inventory-disposals-list',
  icon: 'mdi-truck-delivery-outline',
  titleKey: 'inventory.disposals.title',
  app: 'assets',
  section: INVENTORY_SECTION,
  routes: [
    {
      // The menu links here; the list and a disposal are its pages
      path: 'inventory/disposals',
      name: 'inventory-disposals-list',
      component: RouterView,
      redirect: { name: 'inventory-disposals-index' },
      children: [
        {
          path: '',
          name: 'inventory-disposals-index',
          component: () => import('./DisposalsView.vue'),
        },
        {
          path: ':id(\\d+)',
          name: 'inventory-disposal',
          meta: { titleKey: 'inventory.disposals.disposal' },
          component: () => import('./DisposalView.vue'),
          props: (route) => ({ id: Number(route.params.id) }),
        },
      ],
    },
  ],
}

export const transfers: AppModule = {
  name: 'inventory-transfers',
  icon: 'mdi-swap-horizontal',
  titleKey: 'inventory.transfers.title',
  app: 'assets',
  section: INVENTORY_SECTION,
  routes: [
    {
      // The menu links here; the list and a transfer are its pages
      path: 'inventory/transfers',
      name: 'inventory-transfers',
      component: RouterView,
      redirect: { name: 'inventory-transfers-index' },
      children: [
        {
          path: '',
          name: 'inventory-transfers-index',
          component: () => import('./TransfersView.vue'),
        },
        {
          path: ':id(\\d+)',
          name: 'inventory-transfer',
          meta: { titleKey: 'inventory.transfers.transfer' },
          component: () => import('./TransferView.vue'),
          props: (route) => ({ id: Number(route.params.id) }),
        },
      ],
    },
  ],
}

export const counts: AppModule = {
  name: 'inventory-counts',
  icon: 'mdi-clipboard-list-outline',
  titleKey: 'inventory.counts.title',
  app: 'assets',
  section: INVENTORY_SECTION,
  routes: [
    {
      // The menu links here; the list and a count are its pages
      path: 'inventory/counts',
      name: 'inventory-counts',
      component: RouterView,
      redirect: { name: 'inventory-counts-index' },
      children: [
        {
          path: '',
          name: 'inventory-counts-index',
          component: () => import('./CountsView.vue'),
        },
        {
          path: ':id(\\d+)',
          name: 'inventory-count',
          meta: { titleKey: 'inventory.counts.count' },
          component: () => import('./CountView.vue'),
          props: (route) => ({ id: Number(route.params.id) }),
        },
      ],
    },
  ],
}

export const occurrences = page(
  'inventory-occurrences',
  'occurrences',
  'mdi-alert-circle-outline',
  'inventory.occurrencesPage',
  () => import('./OccurrencesView.vue'),
  false,
)

export const indicators = page(
  'inventory-indicators',
  'indicators',
  'mdi-chart-box-outline',
  'inventory.indicators',
  () => import('./IndicatorsView.vue'),
  false,
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

// Inventory catalogs: what the inspection is measured against
export const INVENTORY_SETTINGS_SECTION = 'menu.sections.inventorySettings'

function settingsPage(
  name: string,
  path: string,
  icon: string,
  key: string,
  view: () => Promise<{ default: Component }>,
) {
  const module = page(name, path, icon, key, view)
  module.section = INVENTORY_SETTINGS_SECTION
  return module
}

export const gradeLevels = settingsPage(
  'inventory-grades',
  'grades',
  'mdi-medal-outline',
  'inventory.grades',
  () => import('./GradeLevelsTab.vue'),
)
export const penalties = settingsPage(
  'inventory-penalties',
  'penalties',
  'mdi-cash-multiple',
  'inventory.penalties',
  () => import('./PenaltyRatesTab.vue'),
)
export const deadlines = settingsPage(
  'inventory-deadlines',
  'deadlines',
  'mdi-calendar-clock-outline',
  'inventory.deadlines',
  () => import('./DeadlinesTab.vue'),
)
export const erasureTools = settingsPage(
  'inventory-erasure-tools',
  'erasure-tools',
  'mdi-harddisk-remove',
  'inventory.erasure',
  () => import('./ErasureToolsTab.vue'),
)

export default [
  appointments,
  receiving,
  inspections,
  blocks,
  disputes,
  stock,
  disposals,
  transfers,
  counts,
  occurrences,
  indicators,
  movement,
  assets,
  accessories,
  locations,
  containers,
  labels,
  gradeLevels,
  penalties,
  erasureTools,
  deadlines,
]
