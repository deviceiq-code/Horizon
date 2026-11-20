import { createPinia, setActivePinia } from 'pinia'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { ApiError } from '@/api'
import { setLanguage } from '@/i18n'
import * as managersApi from '@/modules/account-managers/api'
import { useNotificationsStore } from '@/stores/notifications'
import {
  click,
  dropdownOptions,
  inBody,
  mountWithPlugins,
  openDropdown,
  pickOption,
  settle,
  typeInto,
} from '@/test-utils'
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

const ANA = { id: 7, full_name: 'Ana Souza' }
const BRUNO = { id: 8, full_name: 'Bruno Lima' }
const CARLA = { id: 9, full_name: 'Carla Mendes' }

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
  primary_account_manager: ANA.id,
  primary_account_manager_name: ANA.full_name,
  secondary_account_managers: [BRUNO.id, CARLA.id],
  secondary_account_managers_detail: [BRUNO, CARLA],
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
  primary_account_manager: BRUNO.id,
  primary_account_manager_name: BRUNO.full_name,
  secondary_account_managers: [],
  secondary_account_managers_detail: [],
  is_active: false,
}

const mountView = () => mountWithPlugins(CustomersView)

async function openNew(wrapper: ReturnType<typeof mountView>) {
  await wrapper.find('[data-testid="new"]').trigger('click')
  await settle()
}

async function openEdit(wrapper: ReturnType<typeof mountView>, row: number) {
  await wrapper.findAll('[data-testid="edit"]')[row]!.trigger('click')
  await settle()
}

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
      count: 3,
      next: null,
      previous: null,
      results: [ANA, BRUNO, CARLA].map((m) => ({
        ...m,
        first_name: m.full_name.split(' ')[0] ?? '',
        last_name: m.full_name.split(' ').slice(1).join(' '),
        email: '',
        verticals: [],
        verticals_detail: [],
        photo_version: null,
        created_at: '',
        updated_at: '',
      })),
    })
  })

  afterEach(() => {
    vi.clearAllMocks()
    document.body.innerHTML = ''
  })

  // --- Grid ----------------------------------------------------------------------------------

  it('shows customers with formatted tax ID, location, account managers and status', async () => {
    const wrapper = mountView()
    await settle()

    expect(api.listCustomers).toHaveBeenCalledWith({
      page: 1,
      pageSize: 25,
      search: '',
      ordering: 'name',
    })
    const rows = wrapper.findAll('tbody tr')
    const [alpha, trans] = rows.map((r) => r.text())
    expect(alpha).toContain('12.ABC.345/01DE-35')
    expect(alpha).toContain('Curitiba / PR')
    expect(alpha).toContain('Bruno Lima')
    expect(alpha).toContain('Inactive')
    expect(rows[0]!.find('[data-testid="secondary-count"]').exists()).toBe(false)
    expect(trans).toContain('TransRápido')
    expect(trans).toContain('11.222.333/0001-81')
    expect(trans).toContain('Ana Souza') // primary
    const secondaries = rows[1]!.find('[data-testid="secondary-count"]')
    expect(secondaries.text()).toBe('+2')
    expect(secondaries.attributes('title')).toBe('Bruno Lima, Carla Mendes')
    expect(trans).toContain('Active')
    wrapper.unmount()
  })

  it('sorts the account managers column by the primary account manager', async () => {
    const wrapper = mountView()
    await settle()
    api.listCustomers.mockClear()

    const header = wrapper.findAll('th').find((th) => th.text().includes('Account Managers'))!
    await header.trigger('click')
    await settle()

    expect(api.listCustomers).toHaveBeenLastCalledWith(
      expect.objectContaining({ ordering: 'primary_account_manager__first_name' }),
    )
    wrapper.unmount()
  })

  // --- Form ----------------------------------------------------------------------------------

  it('opens an existing customer with documents formatted and its account managers', async () => {
    api.updateCustomer.mockResolvedValue(BASE)
    const wrapper = mountView()
    await settle()

    await openEdit(wrapper, 1)
    const value = (id: string) => (inBody(`[data-testid="${id}"] input`) as HTMLInputElement).value
    expect(value('name')).toBe('Transportes Rápidos Ltda')
    expect(value('tax-id')).toBe('11.222.333/0001-81')
    expect(inBody('[data-testid="primary-account-manager"]')!.textContent).toContain('Ana Souza')
    const secondaries = inBody('[data-testid="secondary-account-managers"]')!.textContent
    expect(secondaries).toContain('Bruno Lima')
    expect(secondaries).toContain('Carla Mendes')

    await click('save')
    expect(api.updateCustomer).toHaveBeenCalledWith(
      1,
      expect.objectContaining({
        primary_account_manager: ANA.id,
        secondary_account_managers: [BRUNO.id, CARLA.id],
      }),
    )
    wrapper.unmount()
  })

  it('requires the primary account manager', async () => {
    const wrapper = mountView()
    await settle()

    await openNew(wrapper)
    await typeInto('name', 'Beta Locações Ltda')
    await typeInto('tax-id', '11.222.333/0001-81')
    await click('save')

    expect(api.createCustomer).not.toHaveBeenCalled()
    expect(
      inBody('[data-testid="primary-account-manager"]')!.closest('.v-input')!.textContent,
    ).toContain('This field is required.')
    wrapper.unmount()
  })

  it('creates a customer with primary and secondary account managers', async () => {
    api.createCustomer.mockResolvedValue({ ...BASE, id: 3 })
    const wrapper = mountView()
    await settle()

    await openNew(wrapper)
    await typeInto('name', 'Beta Locações Ltda')
    await typeInto('tax-id', '11.222.333/0001-81')
    await pickOption('primary-account-manager', 'Ana Souza')
    await pickOption('secondary-account-managers', 'Carla Mendes')
    await click('save')

    expect(api.createCustomer).toHaveBeenCalledWith(
      expect.objectContaining({
        name: 'Beta Locações Ltda',
        tax_id: '11.222.333/0001-81',
        country: 'BR',
        is_active: true,
        primary_account_manager: ANA.id,
        secondary_account_managers: [CARLA.id],
      }),
    )
    expect(useNotificationsStore().text).toBe('Customer created.')
    wrapper.unmount()
  })

  it('does not offer the primary account manager as a secondary one', async () => {
    const wrapper = mountView()
    await settle()

    await openNew(wrapper)
    await pickOption('primary-account-manager', 'Ana Souza')
    await openDropdown('secondary-account-managers')

    expect(dropdownOptions()).toEqual(['Bruno Lima', 'Carla Mendes'])
    wrapper.unmount()
  })

  it('promoting a secondary to primary removes it from the secondaries', async () => {
    api.updateCustomer.mockResolvedValue(BASE)
    const wrapper = mountView()
    await settle()

    await openEdit(wrapper, 1) // primary Ana; secondaries Bruno and Carla
    await pickOption('primary-account-manager', 'Bruno Lima')
    await click('save')

    expect(api.updateCustomer).toHaveBeenCalledWith(
      1,
      expect.objectContaining({
        primary_account_manager: BRUNO.id,
        secondary_account_managers: [CARLA.id],
      }),
    )
    wrapper.unmount()
  })

  it('requires name and tax ID', async () => {
    const wrapper = mountView()
    await settle()

    await openNew(wrapper)
    await typeInto('email', 'not-an-email')
    await click('save')

    expect(api.createCustomer).not.toHaveBeenCalled()
    expect(document.body.textContent).toContain('This field is required.')
    expect(document.body.textContent).toContain('Enter a valid email address.')
    wrapper.unmount()
  })

  it('shows server validation errors on their fields', async () => {
    api.createCustomer.mockRejectedValue(
      new ApiError(400, 'Bad Request', {
        tax_id: ['Enter a valid CPF or CNPJ.'],
        secondary_account_managers: ['The primary account manager cannot also be a secondary one.'],
      }),
    )
    const wrapper = mountView()
    await settle()

    await openNew(wrapper)
    await typeInto('name', 'Gama')
    await typeInto('tax-id', '123')
    await pickOption('primary-account-manager', 'Ana Souza')
    await click('save')

    expect(document.body.textContent).toContain('Enter a valid CPF or CNPJ.')
    expect(
      inBody('[data-testid="secondary-account-managers"]')!.closest('.v-input')!.textContent,
    ).toContain('The primary account manager cannot also be a secondary one.')
    wrapper.unmount()
  })

  // --- Delete --------------------------------------------------------------------------------

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
