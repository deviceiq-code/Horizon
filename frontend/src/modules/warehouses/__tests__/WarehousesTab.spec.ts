import { createPinia, setActivePinia } from 'pinia'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { setLanguage } from '@/i18n'
import * as verticalsApi from '@/modules/catalogs/verticals/api'
import * as providersApi from '@/modules/service-providers/api'
import { useNotificationsStore } from '@/stores/notifications'
import { click, inBody, mountWithPlugins, pickOption, settle, typeInto } from '@/test-utils'
import * as warehousesApi from '../api'
import WarehousesTab from '../WarehousesTab.vue'

vi.mock('../api', () => ({
  listWarehouses: vi.fn<typeof warehousesApi.listWarehouses>(),
  createWarehouse: vi.fn<typeof warehousesApi.createWarehouse>(),
  updateWarehouse: vi.fn<typeof warehousesApi.updateWarehouse>(),
  deleteWarehouse: vi.fn<typeof warehousesApi.deleteWarehouse>(),
}))
vi.mock('@/modules/service-providers/api', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@/modules/service-providers/api')>()),
  listServiceProviders: vi.fn<typeof providersApi.listServiceProviders>(),
}))
vi.mock('@/modules/catalogs/verticals/api', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@/modules/catalogs/verticals/api')>()),
  listVerticals: vi.fn<typeof verticalsApi.listVerticals>(),
}))

const api = vi.mocked(warehousesApi)
const providers = vi.mocked(providersApi)
const verticals = vi.mocked(verticalsApi)

const IT = { id: 5, name: 'Information Technology', is_enabled: true }

const BARUERI: warehousesApi.Warehouse = {
  id: 1,
  name: 'CD Barueri',
  ownership: 'outsourced',
  service_provider: 3,
  service_provider_detail: { id: 3, name: 'ArmaGerais' },
  verticals: [IT.id],
  verticals_detail: [IT],
  contact_name: 'Ana Souza',
  email: 'ana@example.com',
  phone: '11 4000-0000',
  country: 'BR',
  postal_code: '06460000',
  street: '',
  number: '',
  complement: '',
  district: '',
  city: 'Barueri',
  state: 'SP',
  is_active: true,
  notes: '',
  keywords: [],
  created_at: '',
  updated_at: '',
}

const mountTab = () => mountWithPlugins(WarehousesTab)

describe('WarehousesTab', () => {
  beforeEach(() => {
    setLanguage('en')
    setActivePinia(createPinia())
    api.listWarehouses.mockResolvedValue({
      count: 1,
      next: null,
      previous: null,
      results: [BARUERI],
    })
    verticals.listVerticals.mockResolvedValue({
      count: 1,
      next: null,
      previous: null,
      results: [{ ...IT, sub_verticals: [] } as unknown as verticalsApi.Vertical],
    })
    providers.listServiceProviders.mockResolvedValue({
      count: 1,
      next: null,
      previous: null,
      results: [
        {
          id: 3,
          name: 'Armazéns Gerais Ltda',
          trade_name: 'ArmaGerais',
          tax_id: '11222333000181',
          country: 'BR',
        } as providersApi.ServiceProvider,
      ],
    })
  })

  afterEach(() => {
    vi.clearAllMocks()
    document.body.innerHTML = ''
  })

  it('lists warehouses with operation, provider, verticals, location and contact', async () => {
    const wrapper = mountTab()
    await settle()

    const row = wrapper.find('tbody tr').text()
    expect(row).toContain('CD Barueri')
    expect(row).toContain('Outsourced')
    expect(row).toContain('ArmaGerais')
    expect(row).toContain('Information Technology')
    expect(row).toContain('Barueri / SP')
    expect(row).toContain('11 4000-0000 · ana@example.com')
    wrapper.unmount()
  })

  it('filters by operation and vertical', async () => {
    const wrapper = mountTab()
    await settle()
    const lastFilters = () => api.listWarehouses.mock.lastCall![0].filters

    await click('toggle-filters')
    await pickOption('filter-ownership', 'Own')
    expect(lastFilters()).toEqual({ ownership: 'own' })
    await pickOption('filter-vertical', 'Information Technology')
    expect(lastFilters()).toEqual({ ownership: 'own', vertical: IT.id })
    wrapper.unmount()
  })

  it('requires the business verticals', async () => {
    const wrapper = mountTab()
    await settle()
    await click('new')
    await typeInto('name', 'CD Campinas')
    await click('save')

    expect(api.createWarehouse).not.toHaveBeenCalled()
    expect(inBody('[data-testid="verticals"]')!.closest('.v-input')!.textContent).toContain(
      'Choose at least one business vertical.',
    )
    wrapper.unmount()
  })

  it('an outsourced warehouse picks its service provider among those offering warehousing', async () => {
    api.createWarehouse.mockResolvedValue({ ...BARUERI, id: 2 })
    const wrapper = mountTab()
    await settle()
    await click('new')
    expect(inBody('[data-testid="service-provider"]')).toBeNull() // own by default

    await typeInto('name', 'CD Jundiaí')
    await pickOption('verticals', 'Information Technology')
    inBody('[data-testid="ownership"] button[value="outsourced"]')!.click()
    await settle()
    await click('save')
    expect(api.createWarehouse).not.toHaveBeenCalled() // the provider is required

    await pickOption('service-provider', 'ArmaGerais')
    expect(providers.listServiceProviders).toHaveBeenLastCalledWith(
      expect.objectContaining({ filters: { is_active: true, service: 'warehousing' } }),
    )
    await click('save')
    expect(api.createWarehouse).toHaveBeenCalledWith(
      expect.objectContaining({
        name: 'CD Jundiaí',
        ownership: 'outsourced',
        service_provider: 3,
        verticals: [IT.id],
      }),
    )
    expect(useNotificationsStore().text).toBe('Warehouse created.')
    wrapper.unmount()
  })
})
