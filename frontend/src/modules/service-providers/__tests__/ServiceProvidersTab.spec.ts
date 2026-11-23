import { createPinia, setActivePinia } from 'pinia'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { ApiError } from '@/api'
import { setLanguage } from '@/i18n'
import { useNotificationsStore } from '@/stores/notifications'
import { click, inBody, mountWithPlugins, pickOption, settle, typeInto } from '@/test-utils'
import * as providersApi from '../api'
import ServiceProvidersTab from '../ServiceProvidersTab.vue'

vi.mock('../api', async (importOriginal) => ({
  ...(await importOriginal<typeof import('../api')>()),
  listServiceProviders: vi.fn<typeof providersApi.listServiceProviders>(),
  createServiceProvider: vi.fn<typeof providersApi.createServiceProvider>(),
  updateServiceProvider: vi.fn<typeof providersApi.updateServiceProvider>(),
  deleteServiceProvider: vi.fn<typeof providersApi.deleteServiceProvider>(),
}))

const api = vi.mocked(providersApi)

const STORAGE: providersApi.ServiceProvider = {
  id: 1,
  name: 'Armazéns Gerais Ltda',
  trade_name: 'ArmaGerais',
  tax_id: '11222333000181',
  country: 'BR',
  services: ['warehousing', 'transport'],
  contact_name: 'Ana Souza',
  email: '',
  phone: '',
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
  warehouses_count: 1,
  created_at: '',
  updated_at: '',
}

const mountTab = () => mountWithPlugins(ServiceProvidersTab)

describe('ServiceProvidersTab', () => {
  beforeEach(() => {
    setLanguage('en')
    setActivePinia(createPinia())
    api.listServiceProviders.mockResolvedValue({
      count: 1,
      next: null,
      previous: null,
      results: [STORAGE],
    })
  })

  afterEach(() => {
    vi.clearAllMocks()
    document.body.innerHTML = ''
  })

  it('lists providers with formatted tax ID, services, location and status', async () => {
    const wrapper = mountTab()
    await settle()

    const row = wrapper.find('tbody tr').text()
    expect(row).toContain('Armazéns Gerais Ltda')
    expect(row).toContain('ArmaGerais')
    expect(row).toContain('11.222.333/0001-81')
    expect(row).toContain('Warehousing')
    expect(row).toContain('Transport and Logistics')
    expect(row).toContain('Barueri / SP')
    expect(row).toContain('Active')
    wrapper.unmount()
  })

  it('filters by name and by service', async () => {
    const wrapper = mountTab()
    await settle()
    const lastFilters = () => api.listServiceProviders.mock.lastCall![0].filters

    await click('toggle-filters')
    await typeInto('filter-name', 'arma')
    await new Promise((r) => setTimeout(r, 400))
    await settle()
    expect(lastFilters()).toEqual({ name: 'arma' })
    await pickOption('filter-service', 'Data Erasure')
    expect(lastFilters()).toEqual({ name: 'arma', service: 'data_erasure' })
    wrapper.unmount()
  })

  it('requires at least one service', async () => {
    const wrapper = mountTab()
    await settle()
    await click('new')
    await typeInto('name', 'Logística Rápida')
    await typeInto('tax-id', '11.222.333/0001-81')
    await click('save')

    expect(api.createServiceProvider).not.toHaveBeenCalled()
    expect(inBody('[data-testid="services"]')!.closest('.v-input')!.textContent).toContain(
      'Choose at least one service.',
    )
    wrapper.unmount()
  })

  it('creates a provider with the services chosen', async () => {
    api.createServiceProvider.mockResolvedValue({ ...STORAGE, id: 2 })
    const wrapper = mountTab()
    await settle()
    await click('new')
    await typeInto('name', 'Logística Rápida')
    await typeInto('tax-id', '11.222.333/0001-81')
    await click('service-transport')
    await click('service-warehousing')
    await click('save')

    expect(api.createServiceProvider).toHaveBeenCalledWith(
      expect.objectContaining({
        name: 'Logística Rápida',
        tax_id: '11.222.333/0001-81',
        services: ['transport', 'warehousing'],
        country: 'BR',
        is_active: true,
      }),
    )
    expect(useNotificationsStore().text).toBe('Service provider created.')
    wrapper.unmount()
  })

  it('shows the server error on the services', async () => {
    api.updateServiceProvider.mockRejectedValue(
      new ApiError(400, 'Bad Request', {
        services: ['This provider runs warehouses: warehousing cannot be removed.'],
      }),
    )
    const wrapper = mountTab()
    await settle()
    await wrapper.find('[data-testid="edit"]').trigger('click')
    await settle()
    await click('service-warehousing')
    await click('save')

    expect(inBody('[data-testid="services"]')!.closest('.v-input')!.textContent).toContain(
      'warehousing cannot be removed',
    )
    wrapper.unmount()
  })
})
