import { createPinia, setActivePinia } from 'pinia'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { ApiError } from '@/api'
import { setLanguage } from '@/i18n'
import * as managersApi from '@/modules/account-managers/api'
import { useNotificationsStore } from '@/stores/notifications'
import { click, inBody, mountWithPlugins, settle, typeInto } from '@/test-utils'
import * as customersApi from '../api'
import CustomersView from '../CustomersView.vue'

vi.mock('../api', () => ({
  listCustomers: vi.fn<typeof customersApi.listCustomers>(),
  createCustomer: vi.fn<typeof customersApi.createCustomer>(),
  updateCustomer: vi.fn<typeof customersApi.updateCustomer>(),
  deleteCustomer: vi.fn<typeof customersApi.deleteCustomer>(),
}))
vi.mock('@/modules/account-managers/api', () => ({
  listAccountManagers: vi.fn<typeof managersApi.listAccountManagers>(),
}))

const api = vi.mocked(customersApi)
const managers = vi.mocked(managersApi)

const BASE: customersApi.Customer = {
  id: 1,
  name: 'Transportes Rápidos Ltda',
  trade_name: 'TransRápido',
  tax_id: '11222333000181',
  country: 'BR',
  email: '',
  phone: '',
  postal_code: '13010100',
  street: '',
  number: '',
  complement: '',
  district: '',
  city: 'Campinas',
  state: 'SP',
  account_manager: 7,
  account_manager_name: 'Ana Souza',
  is_active: true,
  notes: '',
  created_at: '',
  updated_at: '',
}
const ALPHA: customersApi.Customer = {
  ...BASE,
  id: 2,
  name: 'Alpha Equipamentos S.A.',
  trade_name: '',
  tax_id: '12ABC34501DE35',
  city: 'Curitiba',
  state: 'PR',
  account_manager: null,
  account_manager_name: null,
  is_active: false,
}

const mountView = () => mountWithPlugins(CustomersView)

describe('CustomersView', () => {
  beforeEach(() => {
    setLanguage('en')
    setActivePinia(createPinia())
    api.listCustomers.mockResolvedValue({
      count: 2,
      next: null,
      previous: null,
      results: [ALPHA, BASE],
    })
    managers.listAccountManagers.mockResolvedValue({
      count: 1,
      next: null,
      previous: null,
      results: [
        {
          id: 7,
          full_name: 'Ana Souza',
          email: 'ana@example.com',
          verticals: [],
          verticals_detail: [],
          created_at: '',
          updated_at: '',
        },
      ],
    })
  })

  afterEach(() => {
    vi.clearAllMocks()
    document.body.innerHTML = ''
  })

  it('shows customers with formatted tax ID, location, account manager and status', async () => {
    const wrapper = mountView()
    await settle()

    expect(api.listCustomers).toHaveBeenCalledWith({
      page: 1,
      pageSize: 25,
      search: '',
      ordering: 'name',
    })
    const rows = wrapper.findAll('tbody tr').map((r) => r.text())
    expect(rows[0]).toContain('12.ABC.345/01DE-35')
    expect(rows[0]).toContain('Curitiba / PR')
    expect(rows[0]).toContain('Inactive')
    expect(rows[1]).toContain('TransRápido')
    expect(rows[1]).toContain('11.222.333/0001-81')
    expect(rows[1]).toContain('Ana Souza')
    expect(rows[1]).toContain('Active')
    wrapper.unmount()
  })

  it('sorts by account manager using the related field name', async () => {
    const wrapper = mountView()
    await settle()
    api.listCustomers.mockClear()

    const header = wrapper.findAll('th').find((th) => th.text().includes('Account manager'))!
    await header.trigger('click')
    await settle()

    expect(api.listCustomers).toHaveBeenLastCalledWith(
      expect.objectContaining({ ordering: 'account_manager__full_name' }),
    )
    wrapper.unmount()
  })

  it('opens an existing customer with documents formatted', async () => {
    const wrapper = mountView()
    await settle()

    await wrapper.findAll('[data-testid="edit"]')[1]!.trigger('click')
    await settle()

    const value = (id: string) => (inBody(`[data-testid="${id}"] input`) as HTMLInputElement).value
    expect(value('name')).toBe('Transportes Rápidos Ltda')
    expect(value('tax-id')).toBe('11.222.333/0001-81')
    expect(document.body.textContent).toContain('Ana Souza')
    wrapper.unmount()
  })

  it('creates a customer with the default country and active status', async () => {
    api.createCustomer.mockResolvedValue({ ...BASE, id: 3 })
    const wrapper = mountView()
    await settle()

    await wrapper.find('[data-testid="new"]').trigger('click')
    await settle()
    await typeInto('name', 'Beta Locações Ltda')
    await typeInto('tax-id', '11.222.333/0001-81')
    await click('save')

    expect(api.createCustomer).toHaveBeenCalledWith(
      expect.objectContaining({
        name: 'Beta Locações Ltda',
        tax_id: '11.222.333/0001-81',
        country: 'BR',
        is_active: true,
        account_manager: null,
      }),
    )
    expect(useNotificationsStore().text).toBe('Customer created.')
    wrapper.unmount()
  })

  it('requires name and tax ID', async () => {
    const wrapper = mountView()
    await settle()

    await wrapper.find('[data-testid="new"]').trigger('click')
    await settle()
    await typeInto('email', 'not-an-email')
    await click('save')

    expect(api.createCustomer).not.toHaveBeenCalled()
    expect(document.body.textContent).toContain('This field is required.')
    expect(document.body.textContent).toContain('Enter a valid email address.')
    wrapper.unmount()
  })

  it('shows the server validation error on the tax ID field', async () => {
    api.createCustomer.mockRejectedValue(
      new ApiError(400, 'Bad Request', { tax_id: ['Enter a valid CPF or CNPJ.'] }),
    )
    const wrapper = mountView()
    await settle()

    await wrapper.find('[data-testid="new"]').trigger('click')
    await settle()
    await typeInto('name', 'Gama')
    await typeInto('tax-id', '123')
    await click('save')

    expect(document.body.textContent).toContain('Enter a valid CPF or CNPJ.')
    wrapper.unmount()
  })

  it('deletes after confirmation', async () => {
    api.deleteCustomer.mockResolvedValue(undefined)
    const wrapper = mountView()
    await settle()

    await wrapper.findAll('[data-testid="delete"]')[0]!.trigger('click')
    await settle()
    expect(document.body.textContent).toContain('Delete "Alpha Equipamentos S.A."?')
    await click('confirm-button')

    expect(api.deleteCustomer).toHaveBeenCalledWith(2)
    expect(useNotificationsStore().text).toBe('Customer deleted.')
    wrapper.unmount()
  })
})
