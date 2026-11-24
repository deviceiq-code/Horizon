import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { i18n, setLanguage } from '@/i18n'
import vuetify from '@/plugins/vuetify'
import { useAuthStore, type User } from '@/stores/auth'
import { inBody, settle } from '@/test-utils'
import * as inventoryApi from '../api'
import CountView from '../CountView.vue'

vi.mock('../api', async (importOriginal) => ({
  ...(await importOriginal<typeof import('../api')>()),
  getCount: vi.fn<typeof inventoryApi.getCount>(),
  listCountReadings: vi.fn<typeof inventoryApi.listCountReadings>(),
  listDivergences: vi.fn<typeof inventoryApi.listDivergences>(),
  readCountAsset: vi.fn<typeof inventoryApi.readCountAsset>(),
  decideDivergence: vi.fn<typeof inventoryApi.decideDivergence>(),
}))

const api = vi.mocked(inventoryApi)

function signIn(roles: string[]) {
  useAuthStore().user = {
    id: 3,
    is_admin: false,
    role_refs: roles.map((key) => ({ key, name: key, is_system: true })),
  } as unknown as User
}

const COUNT = {
  id: 4,
  code: 'INV-2026-0001',
  warehouse: 1,
  warehouse_code: 'SP01',
  warehouse_name: 'CD Barueri',
  kind: 'cyclic',
  status: 'counting',
  responsible: 2,
  responsible_name: 'Sam',
  notes: '',
  locations_count: 2,
  readings_count: 0,
  divergences_count: 0,
  pending_count: 0,
  expected_assets: 0,
  matched_assets: 0,
  accuracy: null,
  created_by_name: 'Sam',
  created_at: '2026-11-24T10:00:00Z',
  closed_by_name: null,
  closed_at: null,
  finished_at: null,
  cancelled_at: null,
  cancel_reason: '',
  location_codes: ['SP01-EST', 'SP01-EST-A1'],
} as inventoryApi.InventoryCountDetail

const mountPage = () =>
  mount(CountView, {
    props: { id: 4 },
    attachTo: document.body,
    global: { plugins: [vuetify, i18n] },
  })

async function scan(wrapper: ReturnType<typeof mountPage>, testid: string, value: string) {
  const input = wrapper.find(`[data-testid="${testid}"] input`).element as HTMLInputElement
  input.value = value
  input.dispatchEvent(new Event('input'))
  await settle()
  input.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', bubbles: true }))
  await settle()
}

describe('inventory count page', () => {
  beforeEach(() => {
    setLanguage('en')
    setActivePinia(createPinia())
    api.listCountReadings.mockResolvedValue([])
  })
  afterEach(() => {
    vi.clearAllMocks()
    document.body.innerHTML = ''
  })

  it('a storekeeper reads the location, then the IDs (blind)', async () => {
    signIn(['storekeeper'])
    api.getCount.mockResolvedValue(COUNT)
    api.readCountAsset.mockResolvedValue([
      {
        id: 1,
        location: 9,
        location_code: 'SP01-EST-A1',
        asset: 5,
        asset_code: 'H000012344',
        accessory_model: null,
        asset_model_label: 'Dell Latitude 5440',
        container: null,
        container_code: null,
        quantity: 1,
        condition: 'good',
        counted_by_name: 'Kim',
        counted_at: '2026-11-24T11:00:00Z',
      },
    ])
    const wrapper = mountPage()
    await settle()
    expect(wrapper.find('[data-testid="count-frozen"]').exists()).toBe(true)
    expect(api.listDivergences).not.toHaveBeenCalled()
    await scan(wrapper, 'count-location', 'SP01-EST-A1')
    await scan(wrapper, 'count-code', 'H000012344')
    expect(api.readCountAsset).toHaveBeenCalledWith(4, 'SP01-EST-A1', 'H000012344')
    expect(wrapper.find('[data-testid="count-feedback"]').text()).toContain('H000012344 counted')
    wrapper.unmount()
  })

  it('a supervisor decides an adjustment with a reason (RN-26)', async () => {
    signIn(['inventory_supervisor'])
    api.getCount.mockResolvedValue({ ...COUNT, status: 'closed', pending_count: 1 })
    const divergence = {
      id: 8,
      kind: 'not_found',
      asset: 5,
      asset_code: 'H000012344',
      asset_status: 'available',
      model_label: 'Dell Latitude 5440',
      condition: '',
      container_code: null,
      expected_location_code: 'SP01-EST-A1',
      found_location_code: null,
      expected_quantity: null,
      counted_quantity: null,
      status: 'pending',
      reason: '',
      decided_by_name: null,
      decided_at: null,
    } as inventoryApi.CountDivergence
    api.listDivergences.mockResolvedValue([divergence])
    api.decideDivergence.mockResolvedValue([{ ...divergence, status: 'approved' }])
    const wrapper = mountPage()
    await settle()
    const row = wrapper.find('[data-testid="count-divergence"]')
    expect(row.text()).toContain('Expected at SP01-EST-A1')
    await row.find('[data-testid="approve"]').trigger('click')
    await settle()
    expect(document.body.textContent).toContain('written off as lost')
    const reason = inBody('[data-testid="decide-reason"] textarea') as HTMLTextAreaElement
    reason.value = 'Searched twice'
    reason.dispatchEvent(new Event('input'))
    await settle()
    ;(inBody('[data-testid="decide-confirm"]') as HTMLButtonElement).click()
    await settle()
    expect(api.decideDivergence).toHaveBeenCalledWith(4, 8, true, 'Searched twice')
    wrapper.unmount()
  })
})
