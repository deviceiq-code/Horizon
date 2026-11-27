import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createMemoryHistory, createRouter } from 'vue-router'

import { i18n, setLanguage } from '@/i18n'
import * as inventoryApi from '@/modules/inventory/api'
import vuetify from '@/plugins/vuetify'
import { click, inBody, settle } from '@/test-utils'
import NotificationsView from '../NotificationsView.vue'

vi.mock('@/modules/inventory/api', () => ({
  listAlerts: vi.fn<typeof inventoryApi.listAlerts>(),
  alertCount: vi.fn<typeof inventoryApi.alertCount>(),
  readAlert: vi.fn<typeof inventoryApi.readAlert>(),
  readAllAlerts: vi.fn<typeof inventoryApi.readAllAlerts>(),
}))
const api = vi.mocked(inventoryApi)

const Blank = { render: () => null }
const ago = (hours: number) => new Date(Date.now() - hours * 3600_000).toISOString()

const ALERTS: inventoryApi.Alert[] = [
  {
    id: 1,
    kind: 'transfer_late',
    severity: 'warning',
    scope: 'user',
    params: { transfer: 'TRF-0001', origin: 'SP01', destination: 'RJ01', days: 2 },
    ref: 'transfer:7',
    created_at: ago(0.2),
    read: false,
  },
  {
    id: 2,
    kind: 'aging',
    severity: 'info',
    scope: 'system',
    params: { asset: 'H1', status: 'blocked', days: 9 },
    ref: 'asset:1',
    created_at: ago(24 * 6),
    read: true,
  },
]

const page = (results: inventoryApi.Alert[], next: string | null = null) => ({
  count: results.length,
  next,
  previous: null,
  results,
})

async function mountPage() {
  const pinia = createPinia()
  setActivePinia(pinia)
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/notifications', name: 'notifications', component: NotificationsView },
      { path: '/transfers/:id', name: 'inventory-transfer', component: Blank },
      { path: '/assets', name: 'inventory-assets', component: Blank },
    ],
  })
  await router.push('/notifications')
  const wrapper = mount(NotificationsView, {
    attachTo: document.body,
    global: { plugins: [vuetify, i18n, pinia, router] },
  })
  await settle()
  return { wrapper, router }
}

describe('NotificationsView', () => {
  beforeEach(() => {
    setLanguage('en')
    api.alertCount.mockResolvedValue({ unread: 1 })
    api.readAlert.mockResolvedValue()
    api.readAllAlerts.mockResolvedValue()
  })
  afterEach(() => {
    vi.clearAllMocks()
    document.body.innerHTML = ''
  })

  it("lists the user's notifications by day: title, message, time, unread marked", async () => {
    api.listAlerts.mockResolvedValue(page(ALERTS))
    const { wrapper } = await mountPage()
    expect(api.listAlerts).toHaveBeenCalledWith(false, 1)
    expect(inBody('[data-testid="tab-unread"]')!.textContent).toContain('Unread (1)')
    expect(inBody('[data-testid="group-today"]')!.textContent).toContain('Today')
    expect(inBody('[data-testid="group-earlier"]')).not.toBeNull()
    expect(inBody('[data-testid="group-yesterday"]')).toBeNull()

    const items = document.querySelectorAll('[data-testid="alert"]')
    expect(items).toHaveLength(2)
    expect(items[0]!.textContent).toContain('Late Transfer')
    expect(items[0]!.textContent).toContain('TRF-0001 (SP01 → RJ01) is 2 days beyond')
    expect(items[0]!.textContent).toContain('minutes ago')
    expect(items[0]!.classList).toContain('unread')
    expect(items[0]!.querySelector('[data-testid="unread-dot"]')).not.toBeNull()
    // Its severity's icon and color; a global notice says "System"
    expect(
      items[0]!.querySelector('[data-testid="severity-warning"] .mdi-alert-outline'),
    ).not.toBeNull()
    expect(items[0]!.querySelector('[data-testid="scope-system"]')).toBeNull()
    expect(
      items[1]!.querySelector('[data-testid="severity-info"] .mdi-information-outline'),
    ).not.toBeNull()
    expect(items[1]!.querySelector('[data-testid="scope-system"]')!.textContent).toContain('System')
    expect(items[1]!.textContent).toContain('Asset Aging')
    expect(items[1]!.textContent).toContain('H1 has been Blocked for 9 days.')
    expect(items[1]!.querySelector('[data-testid="unread-dot"]')).toBeNull()
    wrapper.unmount()
  })

  it('opening one marks it read and goes to its page', async () => {
    api.listAlerts.mockResolvedValue(page(ALERTS))
    const { wrapper, router } = await mountPage()
    ;(document.querySelector('[data-testid="alert"]') as HTMLElement).click()
    await settle()
    expect(api.readAlert).toHaveBeenCalledWith(1)
    expect(router.currentRoute.value.fullPath).toBe('/transfers/7')
    wrapper.unmount()
  })

  it('Unread: only those; Mark All as Read; nothing left: all caught up', async () => {
    api.listAlerts.mockResolvedValue(page(ALERTS))
    const { wrapper } = await mountPage()
    api.listAlerts.mockResolvedValue(page([ALERTS[0]!]))
    await click('tab-unread')
    expect(api.listAlerts).toHaveBeenLastCalledWith(true, 1)
    expect(document.querySelectorAll('[data-testid="alert"]')).toHaveLength(1)

    api.alertCount.mockResolvedValue({ unread: 0 })
    api.listAlerts.mockResolvedValue(page([]))
    await click('read-all')
    expect(api.readAllAlerts).toHaveBeenCalled()
    const empty = inBody('[data-testid="notifications-empty"]')!
    expect(empty.textContent).toContain('No notifications to show')
    expect(empty.textContent).toContain('You are all caught up.')
    expect(empty.querySelector('.mdi-bell-off-outline')).not.toBeNull()
    expect(inBody('[data-testid="read-all"]')!.hasAttribute('disabled')).toBe(true)
    wrapper.unmount()
  })

  it('more than a page: Load More adds the next one', async () => {
    api.listAlerts.mockResolvedValue(page([ALERTS[0]!], 'next'))
    const { wrapper } = await mountPage()
    api.listAlerts.mockResolvedValue(page([ALERTS[1]!]))
    await click('load-more')
    expect(api.listAlerts).toHaveBeenLastCalledWith(false, 2)
    expect(document.querySelectorAll('[data-testid="alert"]')).toHaveLength(2)
    expect(inBody('[data-testid="load-more"]')).toBeNull()
    wrapper.unmount()
  })
})
