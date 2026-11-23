import { createPinia, setActivePinia } from 'pinia'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { setLanguage } from '@/i18n'
import * as warehousesApi from '@/modules/warehouses/api'
import { useAuthStore, type User } from '@/stores/auth'
import { mountWithPlugins, settle } from '@/test-utils'
import * as inventoryApi from '../api'
import AppointmentsView from '../AppointmentsView.vue'
import { dayOf } from '../dates'

vi.mock('../api', async (importOriginal) => ({
  ...(await importOriginal<typeof import('../api')>()),
  listAppointments: vi.fn<typeof inventoryApi.listAppointments>(),
}))
vi.mock('@/modules/warehouses/api', () => ({
  listWarehouses: vi.fn<typeof warehousesApi.listWarehouses>(),
}))
vi.mock('vue-router', async (importOriginal) => ({
  ...(await importOriginal<typeof import('vue-router')>()),
  useRouter: () => ({ push: vi.fn<() => Promise<void>>() }),
}))

const api = vi.mocked(inventoryApi)
const page = <T>(results: T[]) => ({ count: results.length, next: null, previous: null, results })

function at(hour: number) {
  const d = new Date()
  d.setHours(hour, 0, 0, 0)
  return d.toISOString()
}

describe('AppointmentsView', () => {
  beforeEach(() => {
    setLanguage('en')
    setActivePinia(createPinia())
    useAuthStore().user = {
      id: 1,
      is_admin: false,
      role_refs: [{ key: 'remarketing_analyst', name: 'x', is_system: true }],
    } as unknown as User
    vi.mocked(warehousesApi.listWarehouses).mockResolvedValue(page([]))
    api.listAppointments.mockResolvedValue(
      page([
        {
          id: 1,
          code: 'APT-2026-0001',
          kind: 'receiving',
          customer_name: 'TransRápido',
          starts_at: at(9),
          ends_at: at(11),
          status: 'scheduled',
          conflicts: [],
          lot: null,
          warehouse_detail: { id: 1, code: 'SP01', name: 'Garantia' },
        } as unknown as inventoryApi.Appointment,
      ]),
    )
  })

  afterEach(() => {
    vi.clearAllMocks()
    document.body.innerHTML = ''
  })

  it('shows the week with its appointments, asked for the days around today', async () => {
    const wrapper = mountWithPlugins(AppointmentsView)
    await settle()
    const filters = api.listAppointments.mock.lastCall![0].filters!
    expect(String(filters.from) <= dayOf(new Date())).toBe(true)
    expect(String(filters.to) >= dayOf(new Date())).toBe(true)
    expect(wrapper.find('[data-testid="calendar-event"]').text()).toContain('APT-2026-0001')
    expect(wrapper.find('[data-testid="new-appointment"]').exists()).toBe(true)
    wrapper.unmount()
  })
})
