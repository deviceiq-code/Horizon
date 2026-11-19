import { describe, expect, it } from 'vitest'
import { createMemoryHistory, createRouter } from 'vue-router'

import { MODULES } from '@/modules'
import { CATALOG_TABS } from '@/modules/catalogs/tabs'

function makeRouter() {
  return createRouter({
    history: createMemoryHistory(),
    routes: [{ path: '/', children: MODULES.flatMap((m) => m.routes) }],
  })
}

describe('module routes', () => {
  it('every module has a route with its name (the menu links to it)', () => {
    const router = makeRouter()
    const missing = MODULES.map((m) => m.name).filter((name) => !router.hasRoute(name))
    expect(missing).toEqual([])
  })

  it('every catalog tab has a route', () => {
    const router = makeRouter()
    const missing = CATALOG_TABS.map((tab) => tab.name).filter((name) => !router.hasRoute(name))
    expect(missing).toEqual([])
  })

  it('opening Catalogs shows its first tab', async () => {
    const router = makeRouter()
    await router.push({ name: 'catalogs' })
    expect(router.currentRoute.value.name).toBe(CATALOG_TABS[0]!.name)
    expect(router.currentRoute.value.path).toBe('/catalogs/verticals')
  })
})
