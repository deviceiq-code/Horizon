import { createPinia, setActivePinia } from 'pinia'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import AlertsMenu from '@/components/AlertsMenu.vue'
import { setLanguage } from '@/i18n'
import * as inventoryApi from '@/modules/inventory/api'
import { inBody, mountWithPlugins, settle } from '@/test-utils'

vi.mock('@/modules/inventory/api', () => ({
  alertCount: vi.fn<typeof inventoryApi.alertCount>(),
  listAlerts: vi.fn<typeof inventoryApi.listAlerts>(),
  readAlert: vi.fn<typeof inventoryApi.readAlert>(),
  readAllAlerts: vi.fn<typeof inventoryApi.readAllAlerts>(),
}))
vi.mock('vue-router', async (importOriginal) => ({
  ...(await importOriginal<typeof import('vue-router')>()),
  useRouter: () => ({ push: vi.fn<(to: unknown) => Promise<void>>() }),
}))
const api = vi.mocked(inventoryApi)

const OLD: inventoryApi.Alert = {
  id: 1,
  kind: 'aging',
  severity: 'warning',
  scope: 'user',
  params: { asset: 'H1', status: 'blocked', days: 9 },
  ref: 'asset:1',
  created_at: new Date().toISOString(),
  read: false,
}
const NEW: inventoryApi.Alert = {
  ...OLD,
  id: 2,
  kind: 'login_failed',
  severity: 'error',
  params: { username: 'dora', environment: 'live', address: '10.0.0.7' },
  ref: '',
}
const page = (results: inventoryApi.Alert[]) => ({
  count: results.length,
  next: null,
  previous: null,
  results,
})

describe('AlertsMenu: notifications as they happen', () => {
  beforeEach(() => {
    setLanguage('en')
    setActivePinia(createPinia())
    vi.useFakeTimers({ shouldAdvanceTime: true })
  })
  afterEach(() => {
    vi.useRealTimers()
    vi.clearAllMocks()
    document.body.innerHTML = ''
  })

  it('the count follows new ones and the newest pops up (not those already there)', async () => {
    api.alertCount.mockResolvedValue({ unread: 1 })
    api.listAlerts.mockResolvedValue(page([OLD]))
    const wrapper = mountWithPlugins(AlertsMenu)
    await settle()
    expect(inBody('[data-testid="notifications-count"]')!.textContent).toContain('1')
    // Already there when the page opened: nothing pops up
    expect(inBody('[data-testid="notification-toast"] [data-testid="alert"]')).toBeNull()

    api.alertCount.mockResolvedValue({ unread: 2 })
    api.listAlerts.mockResolvedValue(page([NEW, OLD]))
    await vi.advanceTimersByTimeAsync(15_000)
    await settle()
    expect(inBody('[data-testid="notifications-count"]')!.textContent).toContain('2')
    const toast = inBody('[data-testid="alert"]')!
    expect(toast.textContent).toContain('Failed Sign-In')
    expect(toast.querySelector('[data-testid="severity-error"]')).not.toBeNull()
    wrapper.unmount()
  })
})
