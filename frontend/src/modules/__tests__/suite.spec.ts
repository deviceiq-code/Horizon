import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { afterEach, beforeEach, describe, expect, it } from 'vitest'
import { createMemoryHistory, createRouter } from 'vue-router'

import { appName, SUITE_APPS, suiteApp } from '@/apps'
import AppBreadcrumbs from '@/components/AppBreadcrumbs.vue'
import { i18n, setLanguage } from '@/i18n'
import { appModules, MODULES, moduleRoutes } from '@/modules'
import vuetify from '@/plugins/vuetify'
import { useAuthStore } from '@/stores/auth'
import { settle } from '@/test-utils'

const Blank = { render: () => null }

function makeRouter() {
  return createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/', name: 'home', component: Blank },
      { path: '/', component: Blank, children: moduleRoutes() },
    ],
  })
}

describe('suite apps and routes', () => {
  it('every module belongs to an app and lives under its prefix', async () => {
    const router = makeRouter()
    for (const module of MODULES) {
      const app = suiteApp(module.app)!
      expect(app).toBeDefined()
      expect(router.resolve({ name: module.name }).path.startsWith(`/${app.path}/`)).toBe(true)
    }
    expect(router.resolve({ name: 'average-prices' }).path).toBe('/pricing/average-prices')
    expect(router.resolve({ name: 'catalogs-asset-classes' }).path).toBe(
      '/admin/catalogs/asset-classes',
    )
  })

  it('the former addresses take to the new ones', async () => {
    const router = makeRouter()
    await router.push('/average-prices')
    expect(router.currentRoute.value.path).toBe('/pricing/average-prices')
    await router.push('/catalogs/manufacturers')
    expect(router.currentRoute.value.path).toBe('/admin/catalogs/manufacturers')
    await router.push('/users?tab=roles')
    expect(router.currentRoute.value.fullPath).toBe('/admin/users?tab=roles')
  })

  it('Pricing, Remarketing (coming soon) and Administration; menus per app', () => {
    const t = (key: string) => i18n.global.t(key)
    setLanguage('pt-br')
    expect(SUITE_APPS.map((app) => appName(app, t))).toEqual([
      'Pricing',
      'Remarketing',
      'Partners and Programs',
      'Administração',
    ])
    expect(appModules('pricing', false).map((m) => m.name)).toEqual(['average-prices'])
    expect(appModules('admin', true).map((m) => m.name)).toEqual([
      'customers',
      'catalogs',
      'users',
      'system-settings',
    ])
    // Users and System Settings are for administrators
    expect(appModules('admin', false).map((m) => m.name)).toEqual(['customers', 'catalogs'])
    setLanguage('en')
  })
})

describe('AppBreadcrumbs', () => {
  beforeEach(() => {
    setLanguage('en')
    setActivePinia(createPinia())
  })
  afterEach(() => {
    document.body.innerHTML = ''
  })

  async function crumbsAt(path: string) {
    const pinia = createPinia()
    setActivePinia(pinia)
    useAuthStore().user = {
      id: 1,
      username: 'ana',
      name: 'Ana',
      is_admin: true,
      roles: [],
      photo_version: null,
      preferences: {
        language: 'en',
        theme: 'system',
        color_theme: 'metallic_foundations',
        updated_at: '',
      },
    }
    const router = makeRouter()
    await router.push(path)
    const wrapper = mount(AppBreadcrumbs, { global: { plugins: [vuetify, i18n, pinia, router] } })
    await settle()
    const crumbs = wrapper.findAll('[data-testid="crumb"]')
    return {
      wrapper,
      titles: crumbs.map((c) => c.text()),
      links: crumbs.map((c) => {
        const link = c.element.matches('a') ? c.element : c.element.querySelector('a')
        return link?.getAttribute('href') ?? null
      }),
    }
  }

  it('Horizon › Pricing › Average Prices', async () => {
    const { wrapper, titles, links } = await crumbsAt('/pricing/average-prices')
    expect(titles).toEqual(['Horizon', 'Pricing', 'Average Prices'])
    expect(links).toEqual(['/', '/pricing/average-prices', null]) // the page itself is no link
    wrapper.unmount()
  })

  it('a Catalogs tab: Horizon › Administration › Catalogs › Asset Classes', async () => {
    const { wrapper, titles, links } = await crumbsAt('/admin/catalogs/asset-classes')
    expect(titles).toEqual(['Horizon', 'Administration', 'Catalogs', 'Asset Classes'])
    expect(links).toEqual(['/', '/admin/customers', '/admin/catalogs', null])
    wrapper.unmount()
  })
})
