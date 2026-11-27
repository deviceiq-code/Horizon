import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createMemoryHistory, createRouter } from 'vue-router'

import { i18n, setLanguage } from '@/i18n'
import { moduleRoutes } from '@/modules'
import vuetify from '@/plugins/vuetify'
import * as searchModule from '@/search'
import { useAuthStore } from '@/stores/auth'
import { click, inBody, settle } from '@/test-utils'
import SearchView from '../SearchView.vue'

const searchAll = vi.spyOn(searchModule, 'searchAll')
const Blank = { render: () => null }

const RESPONSE: searchModule.SearchResponse = {
  q: 'deere',
  categories: [
    {
      key: 'average_prices',
      count: 6,
      results: [
        {
          id: 20,
          title: 'John Deere 648L-II',
          subtitle: 'Skidder',
          meta: '',
          badge: null,
          search: '648L-II',
          amount: { value: '2500000.00', currency: 'BRL' },
        },
      ],
    },
    {
      key: 'customers',
      count: 1,
      results: [
        {
          id: 7,
          title: 'TransDeere',
          subtitle: 'Transportes Deere Ltda',
          meta: 'Campinas / SP',
          badge: { text: 'Active', color: 'success' },
          search: 'Transportes Deere Ltda',
          amount: null,
        },
      ],
    },
  ],
}

async function mountSearch(path = '/search') {
  const pinia = createPinia()
  setActivePinia(pinia)
  useAuthStore().user = { id: 1, is_admin: false } as never
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/search', name: 'search', component: SearchView },
      { path: '/notifications', name: 'notifications', component: Blank },
      { path: '/settings', name: 'settings', component: Blank },
      { path: '/', component: Blank, children: moduleRoutes() },
    ],
  })
  await router.push(path)
  const wrapper = mount(SearchView, {
    attachTo: document.body,
    global: { plugins: [vuetify, i18n, pinia, router] },
  })
  await settle()
  return { wrapper, router }
}

describe('SearchView', () => {
  beforeEach(() => {
    setLanguage('en')
    vi.useFakeTimers({ shouldAdvanceTime: true })
  })
  afterEach(() => {
    vi.useRealTimers()
    vi.clearAllMocks()
    document.body.innerHTML = ''
  })

  it('before typing: what can be found; nothing searched', async () => {
    const { wrapper } = await mountSearch()
    expect(inBody('[data-testid="search-start"]')!.textContent).toContain('Search Everything')
    expect(searchAll).not.toHaveBeenCalled()
    wrapper.unmount()
  })

  it('the query in the address: counts, tabs and results grouped by category', async () => {
    searchAll.mockResolvedValue(RESPONSE)
    const { wrapper } = await mountSearch('/search?q=deere')
    expect(searchAll).toHaveBeenCalledWith('deere', '')
    expect(inBody('[data-testid="search-count"]')!.textContent).toContain(
      "7 results found for ‘deere’",
    )
    expect(inBody('[data-testid="search-tab-all"]')!.textContent).toContain('All (7)')
    expect(inBody('[data-testid="search-tab-average_prices"]')!.textContent).toContain(
      'Average Prices (6)',
    )
    const prices = inBody('[data-testid="search-group-average_prices"]')!
    expect(prices.textContent).toContain('John Deere 648L-II')
    expect(prices.querySelector('mark')!.textContent).toBe('Deere')
    expect(prices.textContent).toMatch(/R\$\s?2,500,000\.00/)
    // More than shown: "View All (6)" opens its tab
    expect(inBody('[data-testid="search-more-average_prices"]')!.textContent).toContain(
      'View All (6)',
    )
    const customers = inBody('[data-testid="search-group-customers"]')!
    expect(customers.querySelector('[data-testid="search-badge"]')!.textContent).toContain('Active')
    expect(inBody('[data-testid="search-more-customers"]')).toBeNull()
    wrapper.unmount()
  })

  it('a tab asks for more of its category; a result opens its grid searching for it', async () => {
    searchAll.mockResolvedValue(RESPONSE)
    const { wrapper, router } = await mountSearch('/search?q=deere')
    await click('search-more-average_prices')
    await settle()
    expect(searchAll).toHaveBeenLastCalledWith('deere', 'average_prices')
    expect(router.currentRoute.value.query).toEqual({ q: 'deere', category: 'average_prices' })
    // Only that category now
    expect(inBody('[data-testid="search-group-customers"]')).toBeNull()

    await click('search-tab-all')
    await settle()
    const result = inBody('[data-testid="search-group-customers"] [data-testid="search-result"]')
    ;(result as HTMLElement).click()
    // The module's page loads on demand
    await vi.waitFor(() => expect(router.currentRoute.value.name).toBe('customers'))
    expect(router.currentRoute.value.query).toEqual({ search: 'Transportes Deere Ltda' })
    wrapper.unmount()
  })

  it('pages are found by their names, without the server', async () => {
    searchAll.mockResolvedValue({ q: 'notif', categories: [] })
    const { wrapper } = await mountSearch('/search?q=notif')
    const pages = inBody('[data-testid="search-group-pages"]')!
    expect(pages.textContent).toContain('Notifications')
    expect(pages.querySelector('a')!.getAttribute('href')).toBe('/notifications')
    wrapper.unmount()
  })

  it('nothing found', async () => {
    searchAll.mockResolvedValue({ q: 'zzz', categories: [] })
    const { wrapper } = await mountSearch('/search?q=zzzz')
    expect(inBody('[data-testid="search-none"]')!.textContent).toContain('No results found')
    wrapper.unmount()
  })
})
