import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createMemoryHistory, createRouter } from 'vue-router'

import { ApiError } from '@/api'
import { i18n, setLanguage } from '@/i18n'
import * as managersApi from '@/modules/account-managers/api'
import vuetify from '@/plugins/vuetify'
import { useNotificationsStore } from '@/stores/notifications'
import { click, inBody, pickOption, settle, typeInto } from '@/test-utils'
import * as entitiesApi from '../api'
import BusinessEntitiesTab from '../BusinessEntitiesTab.vue'

vi.mock('../api', async (importOriginal) => ({
  ...(await importOriginal<typeof import('../api')>()),
  listBusinessEntities: vi.fn<typeof entitiesApi.listBusinessEntities>(),
  entityCounts: vi.fn<typeof entitiesApi.entityCounts>(),
  parentSuggestion: vi.fn<typeof entitiesApi.parentSuggestion>(),
  createBusinessEntity: vi.fn<typeof entitiesApi.createBusinessEntity>(),
  updateBusinessEntity: vi.fn<typeof entitiesApi.updateBusinessEntity>(),
  deleteBusinessEntity: vi.fn<typeof entitiesApi.deleteBusinessEntity>(),
}))
vi.mock('@/modules/account-managers/api', () => ({
  listAccountManagers: vi.fn<typeof managersApi.listAccountManagers>(),
}))

const api = vi.mocked(entitiesApi)
const managers = vi.mocked(managersApi)

const ANA = { id: 7, full_name: 'Ana Souza' }

const HEAD: entitiesApi.EntityRef = {
  id: 1,
  name: 'Grupo Dell Ltda',
  trade_name: 'Dell',
  tax_id: '11222333000181',
  country: 'BR',
}

const DELL: entitiesApi.BusinessEntity = {
  id: 2,
  name: 'Dell Computadores do Brasil Ltda',
  trade_name: 'Dell Brasil',
  tax_id: '11222333000262',
  country: 'BR',
  parent: HEAD.id,
  parent_detail: HEAD,
  group_detail: HEAD,
  branches_count: 0,
  contact_name: '',
  email: '',
  phone: '',
  postal_code: '',
  street: '',
  number: '',
  complement: '',
  district: '',
  city: 'Eldorado do Sul',
  state: 'RS',
  is_active: true,
  notes: '',
  keywords: [],
  roles: ['customer', 'supplier'],
  customer: {
    id: 10,
    is_active: true,
    contract_types: ['renter'],
    primary_account_manager: ANA.id,
    primary_account_manager_name: ANA.full_name,
    secondary_account_managers: [],
    secondary_account_managers_detail: [],
  },
  supplier: { id: 3, is_active: false, supplies: ['products'] },
  service_provider: null,
  buyer: null,
  created_at: '',
  updated_at: '',
}

const page = <T>(results: T[]) => ({ count: results.length, next: null, previous: null, results })

async function mountView(path = '/') {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [{ path: '/', component: BusinessEntitiesTab }],
  })
  await router.push(path)
  const wrapper = mount(BusinessEntitiesTab, {
    attachTo: document.body,
    global: { plugins: [vuetify, i18n, router] },
  })
  await settle()
  return { wrapper, router }
}

describe('BusinessEntitiesTab', () => {
  beforeEach(() => {
    setLanguage('en')
    setActivePinia(createPinia())
    api.listBusinessEntities.mockResolvedValue(page([DELL]))
    api.entityCounts.mockResolvedValue({
      all: 9,
      customer: 4,
      supplier: 2,
      service_provider: 3,
      buyer: 0,
    })
    api.parentSuggestion.mockResolvedValue(null)
    managers.listAccountManagers.mockResolvedValue(
      page([
        {
          ...ANA,
          first_name: 'Ana',
          last_name: 'Souza',
          email: '',
          verticals: [],
          verticals_detail: [],
          photo_version: null,
          created_at: '',
          updated_at: '',
        },
      ]),
    )
  })

  afterEach(() => {
    vi.clearAllMocks()
    document.body.innerHTML = ''
  })

  it('All: every entity with its roles and head office; counts per tab', async () => {
    const { wrapper } = await mountView()
    expect(api.listBusinessEntities).toHaveBeenCalledWith(
      expect.objectContaining({ ordering: 'name', filters: {} }),
    )
    const tabs = inBody('[data-testid="entity-tabs"]')!.textContent!
    expect(tabs).toContain('All 9')
    expect(tabs).toContain('Customers 4')
    // "All" is the last tab
    expect(tabs.trim().startsWith('Customers 4')).toBe(true)
    expect(tabs.trim().endsWith('All 9')).toBe(true)
    const row = wrapper.find('tbody tr').text()
    expect(row).toContain('11.222.333/0002-62')
    expect(row).toContain('Dell') // its head office
    const roles = wrapper.find('[data-testid="roles-cell"]').text()
    expect(roles).toContain('Customer')
    expect(roles).toContain('Supplier')
    wrapper.unmount()
  })

  it('Customers: their contract types as a column and a filter', async () => {
    const { wrapper } = await mountView('/?tab=customer')
    expect(wrapper.find('[data-testid="contract-types-cell"]').text()).toContain('Renter')
    wrapper.unmount()
  })

  it("a role's tab lists that role's entities, with its columns and its active", async () => {
    const { wrapper, router } = await mountView()
    await click('tab-supplier')
    await settle()
    expect(api.listBusinessEntities).toHaveBeenLastCalledWith(
      expect.objectContaining({ filters: { role: 'supplier' } }),
    )
    expect(router.currentRoute.value.query).toEqual({ tab: 'supplier' })
    const row = wrapper.find('tbody tr').text()
    expect(row).toContain('Products')
    // Inactive as a supplier (though the entity is active)
    expect(row).toContain('Inactive')
    wrapper.unmount()
  })

  it('New in the Customers tab starts with the role; saved with its account manager', async () => {
    api.createBusinessEntity.mockResolvedValue({ ...DELL, id: 5 })
    const { wrapper } = await mountView('/?tab=customer')
    expect(api.listBusinessEntities).toHaveBeenCalledWith(
      expect.objectContaining({ filters: { role: 'customer' } }),
    )
    await wrapper.find('[data-testid="new"]').trigger('click')
    await settle()
    expect(inBody('.v-overlay--active')!.textContent).toContain('New Customer')
    expect((inBody('[data-testid="role-customer"] input') as HTMLInputElement).checked).toBe(true)
    await typeInto('name', 'Acme Ltda')
    await typeInto('tax-id', '44.775.566/0001-60')
    // The account manager and the contract types are in the role's tab
    await click('form-tab-customer')
    await click('contract-type-service_customer')
    await pickOption('primary-account-manager', 'Ana Souza')
    await click('save')
    await settle()
    expect(api.createBusinessEntity).toHaveBeenCalledWith(
      expect.objectContaining({
        name: 'Acme Ltda',
        tax_id: '44.775.566/0001-60',
        parent: null,
        customer: {
          is_active: true,
          contract_types: ['service_customer'],
          primary_account_manager: 7,
          secondary_account_managers: [],
        },
      }),
    )
    const sent = api.createBusinessEntity.mock.calls[0]![0]
    expect('supplier' in sent).toBe(false) // roles never turned on are not sent
    expect(useNotificationsStore().text).toBe('Business entity created.')
    expect(api.entityCounts).toHaveBeenCalledTimes(2) // the counts follow
    wrapper.unmount()
  })

  it('a role turned off is removed; the server refusing it (in use) is shown', async () => {
    api.updateBusinessEntity.mockRejectedValueOnce(
      new ApiError(409, 'This entity is the customer of analyses: deactivate it instead.', {}),
    )
    const { wrapper } = await mountView()
    await wrapper.find('[data-testid="edit"]').trigger('click')
    await settle()
    // Its roles open their tabs
    expect(inBody('[data-testid="form-tab-customer"]')).not.toBeNull()
    expect(inBody('[data-testid="form-tab-supplier"]')).not.toBeNull()
    ;(inBody('[data-testid="role-customer"] input') as HTMLInputElement).click()
    await settle()
    expect(inBody('[data-testid="form-tab-customer"]')).toBeNull()
    await click('save')
    await settle()
    expect(api.updateBusinessEntity).toHaveBeenCalledWith(
      2,
      expect.objectContaining({
        customer: null,
        supplier: { is_active: false, supplies: ['products'] },
        parent: 1,
      }),
    )
    expect(inBody('[data-testid="general-error"]')!.textContent).toContain('deactivate it')
    wrapper.unmount()
  })

  it('a branch CNPJ suggests the head office with the same root', async () => {
    api.parentSuggestion.mockResolvedValue(HEAD)
    api.createBusinessEntity.mockResolvedValue({ ...DELL, id: 6 })
    const { wrapper } = await mountView()
    await wrapper.find('[data-testid="new"]').trigger('click')
    await settle()
    await typeInto('name', 'Dell Filial 3')
    await typeInto('tax-id', '11.222.333/0003-43')
    inBody('[data-testid="tax-id"] input')!.dispatchEvent(new Event('blur'))
    await settle()
    expect(api.parentSuggestion).toHaveBeenCalledWith('BR', '11.222.333/0003-43', undefined)
    expect(inBody('[data-testid="parent-suggestion"]')!.textContent).toContain('Dell')
    await click('use-suggestion')
    await settle()
    expect(inBody('[data-testid="parent-suggestion"]')).toBeNull()
    await click('save')
    await settle()
    expect(api.createBusinessEntity).toHaveBeenCalledWith(
      expect.objectContaining({ parent: HEAD.id }),
    )
    wrapper.unmount()
  })
})
