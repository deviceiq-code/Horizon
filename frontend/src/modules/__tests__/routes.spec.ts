import { describe, expect, it } from 'vitest'
import { createMemoryHistory, createRouter } from 'vue-router'

import { MODULES, visibleModules } from '@/modules'

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

  it('Administration modules are in the Management and Catalogs sections', () => {
    const admin = MODULES.filter((m) => m.app === 'admin').map((m) => [m.name, m.section])
    expect(admin).toEqual([
      ['customers', 'menu.sections.management'],
      ['users', 'menu.sections.management'],
      ['roles', 'menu.sections.management'],
      ['system-settings', 'menu.sections.management'],
      ['catalogs-verticals', 'menu.sections.catalogs'],
      ['catalogs-asset-classes', 'menu.sections.catalogs'],
      ['catalogs-manufacturers', 'menu.sections.catalogs'],
    ])
  })

  it('the former Catalogs page opens its first table', async () => {
    const router = makeRouter()
    await router.push({ name: 'catalogs' })
    expect(router.currentRoute.value.name).toBe('catalogs-verticals')
    expect(router.currentRoute.value.path).toBe('/catalogs/verticals')
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
