import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import type { Component } from 'vue'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { i18n, setLanguage } from '@/i18n'
import vuetify from '@/plugins/vuetify'
import { useAuthStore, type User } from '@/stores/auth'
import { settle } from '@/test-utils'
import * as inventoryApi from '../api'
import DisposalView from '../DisposalView.vue'
import StockView from '../StockView.vue'

vi.mock('../api', async (importOriginal) => ({
  ...(await importOriginal<typeof import('../api')>()),
  getDisposal: vi.fn<typeof inventoryApi.getDisposal>(),
  addDisposalAssets: vi.fn<typeof inventoryApi.addDisposalAssets>(),
  pickDisposalAsset: vi.fn<typeof inventoryApi.pickDisposalAsset>(),
  shipDisposal: vi.fn<typeof inventoryApi.shipDisposal>(),
  stockGroups: vi.fn<typeof inventoryApi.stockGroups>(),
  stockAssets: vi.fn<typeof inventoryApi.stockAssets>(),
}))
vi.mock('@/modules/warehouses/api', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@/modules/warehouses/api')>()),
  listWarehouses: vi.fn<() => Promise<unknown>>(async () => ({ count: 0, next: null, previous: null, results: [] })),
}))

const api = vi.mocked(inventoryApi)

function mountPage(component: Component, props: Record<string, unknown> = {}) {
  return mount(component, {
    props,
    attachTo: document.body,
    global: { plugins: [vuetify, i18n], stubs: { RouterLink: { template: '<a><slot /></a>' } } },
  })
}

function signIn(roles: string[]) {
  useAuthStore().user = {
    id: 3,
    is_admin: false,
    role_refs: roles.map((key) => ({ key, name: key, is_system: true })),
  } as unknown as User
}

const ITEM = {
  id: 11,
  asset: 1,
  asset_detail: {
    id: 1,
    horizon_id: 'H000000018',
    model: 'Dell Latitude 5440',
    serial: 'ABC1234',
    status: 'reserved',
    customer: 'TransRápido',
    lot: 'LOT-2026-0001',
    location: 'SP01-EST-A1',
    asset_class: 'Notebook',
    grade: 'B1C',
    held_for_dispute: false,
    area_type: 'stock',
  },
  accessory_model: null,
  accessory_model_label: null,
  quantity: 1,
  condition: 'good',
  unit_value: '1500.00',
  line_total: '1500.00',
  picked_quantity: 0,
  picked: false,
  picked_at: null,
  picked_by_name: null,
} as inventoryApi.DisposalItem

function detail(overrides: Partial<inventoryApi.DisposalDetail> = {}) {
  return {
    id: 7,
    code: 'DSP-2026-0001',
    kind: 'lessee_sale',
    status: 'reserved',
    warehouse: 1,
    warehouse_code: 'SP01',
    warehouse_name: 'CD Barueri',
    customer: 4,
    customer_name: 'TransRápido',
    contract: '',
    discard_provider: null,
    discard_provider_name: null,
    appointment: null,
    appointment_code: null,
    document_number: '',
    notes: '',
    keywords: [],
    items_count: 1,
    picked_count: 0,
    created_by_name: 'Carla',
    created_at: '2026-11-24T10:00:00Z',
    updated_at: '2026-11-24T10:00:00Z',
    shipped_by_name: null,
    shipped_at: null,
    cancelled_by_name: null,
    cancelled_at: null,
    cancel_reason: '',
    items: [ITEM],
    files: [],
    totals: { assets: 1, accessories: 0, total_value: '1500.00' },
    problems: ['1 item(s) not picked yet: read each one against the list.'],
    ...overrides,
  } as inventoryApi.DisposalDetail
}

async function type(input: HTMLInputElement, value: string) {
  input.value = value
  input.dispatchEvent(new Event('input'))
  await settle()
  input.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', bubbles: true }))
  await settle()
}

describe('disposal page', () => {
  beforeEach(() => {
    setLanguage('en')
    setActivePinia(createPinia())
  })
  afterEach(() => {
    vi.clearAllMocks()
    document.body.innerHTML = ''
  })

  it('commercial adds an asset by reading its ID; no picking for them', async () => {
    signIn(['commercial_finance'])
    api.getDisposal.mockResolvedValue(detail({ items: [], items_count: 0 }))
    api.addDisposalAssets.mockResolvedValue(detail())
    const wrapper = mountPage(DisposalView, { id: 7 })
    await settle()
    expect(wrapper.find('[data-testid="tab-picking"]').exists()).toBe(false)
    expect(wrapper.find('[data-testid="disposal-ship"]').exists()).toBe(false)
    await type(
      wrapper.find('[data-testid="disposal-add-code"] input').element as HTMLInputElement,
      'H000000018',
    )
    expect(api.addDisposalAssets).toHaveBeenCalledWith(7, ['H000000018'], null)
    expect(wrapper.findAll('[data-testid="disposal-item"]')).toHaveLength(1)
    expect(wrapper.find('[data-testid="disposal-problems"]').text()).toContain('not picked')
    wrapper.unmount()
  })

  it('a storekeeper picks against the list after reading the shipping area', async () => {
    signIn(['storekeeper'])
    api.getDisposal.mockResolvedValue(detail())
    api.pickDisposalAsset.mockResolvedValue(
      detail({
        status: 'picking',
        items: [{ ...ITEM, picked: true, picked_quantity: 1 }],
        problems: [],
      }),
    )
    const wrapper = mountPage(DisposalView, { id: 7 })
    await settle()
    expect(wrapper.find('[data-testid="disposal-ship"]').attributes('disabled')).toBeDefined()
    await wrapper.find('[data-testid="tab-picking"]').trigger('click')
    await settle()
    const code = wrapper.find('[data-testid="pick-code"] input').element as HTMLInputElement
    expect(code.disabled).toBe(true) // the shipping area first
    await type(
      wrapper.find('[data-testid="pick-shipping"] input').element as HTMLInputElement,
      'SP01-EXP',
    )
    await type(code, 'H000000018')
    expect(api.pickDisposalAsset).toHaveBeenCalledWith(7, 'H000000018', 'SP01-EXP')
    expect(wrapper.find('[data-testid="pick-feedback"]').text()).toContain('H000000018 picked')
    expect(wrapper.find('[data-testid="disposal-ship"]').attributes('disabled')).toBeUndefined()
    wrapper.unmount()
  })

  it('a wrong reading is refused with the reason', async () => {
    signIn(['storekeeper'])
    api.getDisposal.mockResolvedValue(detail())
    const { ApiError } = await import('@/api')
    api.pickDisposalAsset.mockRejectedValue(
      new ApiError(400, 'H000000026 is not in this disposal.', {
        detail: 'H000000026 is not in this disposal.',
        field: 'code',
      }),
    )
    const wrapper = mountPage(DisposalView, { id: 7 })
    await settle()
    await wrapper.find('[data-testid="tab-picking"]').trigger('click')
    await settle()
    await type(
      wrapper.find('[data-testid="pick-shipping"] input').element as HTMLInputElement,
      'SP01-EXP',
    )
    await type(
      wrapper.find('[data-testid="pick-code"] input').element as HTMLInputElement,
      'H000000026',
    )
    expect(wrapper.find('[data-testid="pick-feedback"]').text()).toContain('not in this disposal')
    wrapper.unmount()
  })

  it('ships when nothing is missing', async () => {
    signIn(['storekeeper'])
    api.getDisposal.mockResolvedValue(
      detail({ status: 'picking', problems: [], items: [{ ...ITEM, picked: true }] }),
    )
    api.shipDisposal.mockResolvedValue(detail({ status: 'shipped', problems: [] }))
    const wrapper = mountPage(DisposalView, { id: 7 })
    await settle()
    await wrapper.find('[data-testid="disposal-ship"]').trigger('click')
    await settle()
    expect(api.shipDisposal).toHaveBeenCalledWith(7)
    expect(wrapper.find('[data-testid="disposal-status"]').text()).toBe('Shipped')
    wrapper.unmount()
  })
})

describe('stock', () => {
  beforeEach(() => {
    setLanguage('en')
    setActivePinia(createPinia())
    signIn([])
  })
  afterEach(() => {
    vi.clearAllMocks()
    document.body.innerHTML = ''
  })

  it('lists the groups with the total and opens a group to its units', async () => {
    api.stockGroups.mockResolvedValue([
      {
        asset_class: 1,
        asset_class_name: 'Notebook',
        asset_model: 2,
        model: 'Dell Latitude 5440',
        grade: 'B1C',
        status: 'available',
        warehouse: 1,
        warehouse_code: 'SP01',
        units: 3,
        oldest_entry: '2026-11-01T10:00:00Z',
        average_days: 12,
        max_days: 23,
      },
    ])
    api.stockAssets.mockResolvedValue({
      count: 1,
      next: null,
      previous: null,
      results: [
        {
          id: 9,
          horizon_id: 'H000000018',
          serial: 'ABC1234',
          model: 'Dell Latitude 5440',
          asset_class: 'Notebook',
          specs: [],
          status: 'available',
          condition_grade: 'B1C',
          held_for_dispute: false,
          warehouse: 'SP01',
          location: 'SP01-EST-A1',
          customer: 'TransRápido',
          lot: 'LOT-2026-0001',
          created_at: '2026-11-01T10:00:00Z',
          days_in_stock: 23,
          report: {
            id: 5,
            version: 1,
            conservation: 'B',
            functioning: '1',
            completeness: 'P',
            missing_items: ['Charger'],
            approved_at: '2026-11-03T10:00:00Z',
          },
          disposal: null,
        },
      ],
    })
    const wrapper = mountPage(StockView)
    await settle()
    expect(api.stockGroups).toHaveBeenCalledWith(expect.objectContaining({ status: 'available' }))
    expect(wrapper.find('[data-testid="stock-total"]').text()).toBe('3')
    await wrapper.find('[data-testid="stock-group"]').trigger('click')
    await settle()
    expect(api.stockAssets).toHaveBeenCalledWith(
      expect.objectContaining({ asset_model: 2, grade: 'B1C', warehouse: 1 }),
      1,
      200,
    )
    const unit = wrapper.find('[data-testid="stock-unit"]').text()
    expect(unit).toContain('H000000018')
    expect(unit).toContain('B1P · v1')
    expect(unit).toContain('Charger')
    wrapper.unmount()
  })
})
