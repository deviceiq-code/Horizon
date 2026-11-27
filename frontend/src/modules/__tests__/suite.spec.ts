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
    expect(router.resolve({ name: 'efmv-analysis', params: { id: 3 } }).path).toBe(
      '/pricing/efmv-analyses/3',
    )
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
    // The former Roles tab is a page of its own
    await router.push('/users?tab=roles')
    expect(router.currentRoute.value.fullPath).toBe('/admin/roles')
    await router.push('/admin/catalogs')
    expect(router.currentRoute.value.path).toBe('/admin/catalogs/verticals')
  })

  it('Pricing, Remarketing, Services and Partnerships and Administration; menus per app', () => {
    const t = (key: string) => i18n.global.t(key)
    setLanguage('pt-br')
    expect(SUITE_APPS.map((app) => appName(app, t))).toEqual([
      'Pricing',
      'Remarketing',
      'Services and Partnerships',
      'Administração',
    ])
    expect(appModules('pricing', false).map((m) => m.name)).toEqual([
      'efmv-analyses',
      'average-prices',
    ])
    expect(appModules('partners', false).map((m) => m.name)).toEqual([
      'partners-services',
      'partners-partners',
      'partners-incentives',
      'partners-discounts',
    ])
    expect(appModules('remarketing', false).map((m) => m.name)).toEqual([
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
      'inventory-grades',
      'inventory-penalties',
      'inventory-erasure-tools',
      'inventory-deadlines',
      'warehouses',
    ])
    expect(appModules('admin', true).map((m) => m.name)).toEqual([
      'users',
      'roles',
      'customers',
      'service-providers',
      'catalogs-verticals',
      'catalogs-asset-classes',
      'catalogs-asset-models',
      'catalogs-manufacturers',
    ])
    // Users, Roles and System Settings are for administrators
    expect(appModules('admin', false).map((m) => m.name)).toEqual([
      'customers',
      'service-providers',
      'catalogs-verticals',
      'catalogs-asset-classes',
      'catalogs-asset-models',
      'catalogs-manufacturers',
    ])
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
        ui_scale: 'auto',
        date_format: 'auto',
        time_format: 'auto',
        select_on_focus: true,
        word_dictionary: true,
        auto_scope: true,
        scope_threshold: '5.00',
        number_format: 'auto',
        percent_places: 2,
        currency: 'BRL',
        currency_display: 'symbol',
        ui_state: {},
        user_name_display: 'full_name',
        full_name_order: 'first_last',
        searxng_url: '',
        web_search: true,
        web_search_engine: 'google',
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
    // The app links to its first page (eFMV Analyses); the page itself is no link
    expect(links).toEqual(['/', '/pricing/efmv-analyses', null])
    wrapper.unmount()
  })

  it('a catalog: Horizon › Administration › Asset Classes', async () => {
    const { wrapper, titles, links } = await crumbsAt('/admin/catalogs/asset-classes')
    expect(titles).toEqual(['Horizon', 'Administration', 'Asset Classes'])
    // The app links to its first page (administrators: Users)
    expect(links).toEqual(['/', '/admin/users', null])
    wrapper.unmount()
  })
})
