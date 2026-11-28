import { describe, expect, it } from 'vitest'
import { createMemoryHistory, createRouter } from 'vue-router'

import { MODULES, moduleRoutes, visibleModules } from '@/modules'

function makeRouter() {
  return createRouter({
    history: createMemoryHistory(),
    routes: [{ path: '/', children: MODULES.flatMap((m) => m.routes) }],
  })
}

describe('module routes', () => {
  it('Asset Management was the Remarketing app: its former addresses open the same pages', async () => {
    const router = createRouter({
      history: createMemoryHistory(),
      routes: [{ path: '/', children: moduleRoutes() }],
    })
    await router.push('/remarketing/inventory/stock?warehouse=2')
    expect(router.currentRoute.value.name).toBe('inventory-stock')
    expect(router.currentRoute.value.fullPath).toBe('/asset-management/inventory/stock?warehouse=2')
    await router.push('/remarketing/inventory/warehouses')
    expect(router.currentRoute.value.name).toBe('warehouses')
    // The new Remarketing app has pages of its own
    await router.push('/remarketing/offers')
    expect(router.currentRoute.value.name).toBe('remarketing-offers')
    expect(router.currentRoute.value.path).toBe('/remarketing/offers')
  })

  it('every module has a route with its name (the menu links to it)', () => {
    const router = makeRouter()
    const missing = MODULES.map((m) => m.name).filter((name) => !router.hasRoute(name))
    expect(missing).toEqual([])
  })

  it('Administration modules are in the Management and Catalogs sections', () => {
    const admin = MODULES.filter((m) => m.app === 'admin').map((m) => [m.name, m.section])
    expect(admin).toEqual([
      ['users', 'menu.sections.management'],
      ['roles', 'menu.sections.management'],
      ['business-entities', 'menu.sections.catalogs'],
      ['catalogs-verticals', 'menu.sections.catalogs'],
      ['catalogs-asset-classes', 'menu.sections.catalogs'],
      ['catalogs-asset-models', 'menu.sections.catalogs'],
      ['catalogs-manufacturers', 'menu.sections.catalogs'],
    ])
  })

  it('the former Catalogs page opens its first table', async () => {
    const router = makeRouter()
    await router.push({ name: 'catalogs' })
    expect(router.currentRoute.value.name).toBe('catalogs-verticals')
    expect(router.currentRoute.value.path).toBe('/catalogs/verticals')
  })

  it('Inventory opens Appointments; its pages are in the Asset Management app', async () => {
    const router = makeRouter()
    await router.push('/inventory')
    expect(router.currentRoute.value.name).toBe('inventory-appointments')
    const assets = MODULES.filter((m) => m.app === 'assets')
    expect(assets.map((m) => [m.name, m.section])).toEqual([
      ...[
        'inventory-appointments',
        'inventory-receiving',
        'inventory-inspections',
        'inventory-blocks',
        'inventory-disputes',
        'inventory-stock',
        'inventory-disposals-list',
        'inventory-transfers',
        'inventory-counts',
        'inventory-occurrences',
        'inventory-indicators',
        'inventory-movement',
        'inventory-assets',
        'inventory-accessories',
        'inventory-locations',
        'inventory-containers',
        'inventory-labels',
      ].map((name) => [name, 'menu.sections.inventory']),
      ...[
        'inventory-grades',
        'inventory-penalties',
        'inventory-erasure-tools',
        'inventory-deadlines',
      ].map((name) => [name, 'menu.sections.inventorySettings']),
      ['warehouses', 'menu.sections.inventory'],
    ])
  })

  it('a report opens under Inspection', async () => {
    const router = makeRouter()
    await router.push('/inventory/inspection/3')
    expect(router.currentRoute.value.name).toBe('inventory-report')
  })

  it('a lot opens under Receiving', async () => {
    const router = makeRouter()
    await router.push('/inventory/receiving/7')
    expect(router.currentRoute.value.name).toBe('inventory-lot')
  })

  it('the former Roles tab opens the Roles page', async () => {
    const router = makeRouter()
    await router.push('/users?tab=roles')
    expect(router.currentRoute.value.name).toBe('roles')
  })

  it('administrator-only modules are hidden from other users', () => {
    expect(visibleModules(true).map((m) => m.name)).toContain('users')
    expect(visibleModules(false).map((m) => m.name)).not.toContain('users')
  })
})
