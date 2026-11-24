import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { ApiError } from '@/api'
import { i18n, setLanguage } from '@/i18n'
import vuetify from '@/plugins/vuetify'
import { useAuthStore, type User } from '@/stores/auth'
import { settle } from '@/test-utils'
import * as inventoryApi from '../api'
import TransferView from '../TransferView.vue'

vi.mock('../api', async (importOriginal) => ({
  ...(await importOriginal<typeof import('../api')>()),
  getTransfer: vi.fn<typeof inventoryApi.getTransfer>(),
  approveTransfer: vi.fn<typeof inventoryApi.approveTransfer>(),
  pickTransfer: vi.fn<typeof inventoryApi.pickTransfer>(),
  receiveTransfer: vi.fn<typeof inventoryApi.receiveTransfer>(),
}))

const api = vi.mocked(inventoryApi)

function signIn(roles: string[]) {
  useAuthStore().user = {
    id: 3,
    is_admin: false,
    role_refs: roles.map((key) => ({ key, name: key, is_system: true })),
  } as unknown as User
}

function mountPage() {
  return mount(TransferView, {
    props: { id: 5 },
    attachTo: document.body,
    global: { plugins: [vuetify, i18n] },
  })
}

const ITEM = {
  id: 21,
  asset: 1,
  asset_detail: {
    id: 1,
    horizon_id: 'H000000018',
    model: 'Dell Latitude 5440',
    serial: 'ABC1234',
    status: 'available',
    customer: null,
    lot: null,
    location: 'SP01-EST-A1',
    asset_class: 'Notebook',
    grade: 'B1C',
    held_for_dispute: false,
    container: null,
  },
  accessory_model: null,
  accessory_model_label: null,
  quantity: 1,
  condition: 'good',
  status_before: '',
  container: null,
  container_code: null,
  picked_quantity: 0,
  picked: false,
  picked_at: null,
  received_quantity: 0,
  received: false,
  received_at: null,
  received_location_code: null,
} as inventoryApi.TransferItem

function detail(overrides: Partial<inventoryApi.TransferDetail> = {}) {
  return {
    id: 5,
    code: 'TRF-2026-0001',
    origin: 1,
    origin_code: 'SP01',
    origin_name: 'CD Barueri',
    destination: 2,
    destination_code: 'PE01',
    destination_name: 'CD Recife',
    reason: 'Sell in the Northeast',
    status: 'requested',
    fiscal_document_number: '',
    transit_days: 5,
    notes: '',
    keywords: [],
    items_count: 1,
    picked_count: 0,
    received_count: 0,
    requested_by_name: 'Ana',
    requested_at: '2026-11-24T10:00:00Z',
    approved_by_name: null,
    approved_at: null,
    sent_by_name: null,
    sent_at: null,
    received_by_name: null,
    received_at: null,
    cancelled_by_name: null,
    cancelled_at: null,
    cancel_reason: '',
    days_late: 0,
    updated_at: '2026-11-24T10:00:00Z',
    items: [ITEM],
    files: [],
    occurrences: [],
    problems: ['A supervisor must approve the transfer.'],
    ...overrides,
  } as inventoryApi.TransferDetail
}

async function scan(wrapper: ReturnType<typeof mountPage>, testid: string, value: string) {
  const input = wrapper.find(`[data-testid="${testid}"] input`).element as HTMLInputElement
  input.value = value
  input.dispatchEvent(new Event('input'))
  await settle()
  input.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', bubbles: true }))
  await settle()
}

describe('transfer page', () => {
  beforeEach(() => {
    setLanguage('en')
    setActivePinia(createPinia())
  })
  afterEach(() => {
    vi.clearAllMocks()
    document.body.innerHTML = ''
  })

  it('only supervisors approve; analysts see what is missing', async () => {
    signIn(['remarketing_analyst'])
    api.getTransfer.mockResolvedValue(detail())
    let wrapper = mountPage()
    await settle()
    expect(wrapper.find('[data-testid="transfer-approve"]').exists()).toBe(false)
    expect(wrapper.find('[data-testid="transfer-problems"]').text()).toContain('approve')
    wrapper.unmount()

    signIn(['inventory_supervisor'])
    api.approveTransfer.mockResolvedValue(detail({ status: 'approved', problems: [] }))
    wrapper = mountPage()
    await settle()
    await wrapper.find('[data-testid="transfer-approve"]').trigger('click')
    await settle()
    expect(api.approveTransfer).toHaveBeenCalledWith(5)
    expect(wrapper.find('[data-testid="transfer-status"]').text()).toBe('Approved')
    wrapper.unmount()
  })

  it('a storekeeper picks against the list', async () => {
    signIn(['storekeeper'])
    api.getTransfer.mockResolvedValue(detail({ status: 'approved' }))
    api.pickTransfer.mockResolvedValue(
      detail({ status: 'picking', items: [{ ...ITEM, picked: true, picked_quantity: 1 }] }),
    )
    const wrapper = mountPage()
    await settle()
    await wrapper.find('[data-testid="tab-picking"]').trigger('click')
    await settle()
    await scan(wrapper, 'pick-code', 'H000000018')
    expect(api.pickTransfer).toHaveBeenCalledWith(5, 'H000000018')
    expect(wrapper.find('[data-testid="pick-feedback"]').text()).toContain('H000000018 picked')
    wrapper.unmount()
  })

  it('receives after the location, noting damage; a surplus shows the reason', async () => {
    signIn(['receiver'])
    const inTransit = detail({ status: 'in_transit', problems: [] })
    api.getTransfer.mockResolvedValue(inTransit)
    api.receiveTransfer.mockResolvedValueOnce(
      detail({ status: 'in_transit', items: [{ ...ITEM, received: true, received_quantity: 1 }] }),
    )
    const wrapper = mountPage()
    await settle()
    await wrapper.find('[data-testid="tab-receiving"]').trigger('click')
    await settle()
    const code = wrapper.find('[data-testid="receive-code"] input').element as HTMLInputElement
    expect(code.disabled).toBe(true)
    await scan(wrapper, 'receive-location', 'PE01-EST')
    await wrapper.find('[data-testid="receive-damaged"] input').setValue(true)
    await settle()
    await scan(wrapper, 'receive-code', 'H000000018')
    expect(api.receiveTransfer).toHaveBeenCalledWith(5, {
      location: 'PE01-EST',
      code: 'H000000018',
      damaged: true,
      note: '',
    })
    api.receiveTransfer.mockRejectedValueOnce(
      new ApiError(400, 'H000000026 is not in this transfer: recorded as a surplus.', {
        detail: 'H000000026 is not in this transfer: recorded as a surplus.',
        field: 'code',
      }),
    )
    await scan(wrapper, 'receive-code', 'H000000026')
    expect(wrapper.find('[data-testid="receive-feedback"]').text()).toContain('surplus')
    wrapper.unmount()
  })
})
