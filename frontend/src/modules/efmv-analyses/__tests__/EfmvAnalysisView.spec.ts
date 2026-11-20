import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createMemoryHistory, createRouter } from 'vue-router'

import { ApiError } from '@/api'
import { i18n, setLanguage } from '@/i18n'
import * as managersApi from '@/modules/account-managers/api'
import * as pricesApi from '@/modules/average-prices/api'
import * as customersApi from '@/modules/customers/api'
import vuetify from '@/plugins/vuetify'
import { useAuthStore } from '@/stores/auth'
import { click, inBody, pickOption, settle, typeInto } from '@/test-utils'
import * as efmvApi from '../api'
import EfmvAnalysisView from '../EfmvAnalysisView.vue'

vi.mock('../api', () => ({
  getEfmvAnalysis: vi.fn<typeof efmvApi.getEfmvAnalysis>(),
  createEfmvAnalysis: vi.fn<typeof efmvApi.createEfmvAnalysis>(),
  updateEfmvAnalysis: vi.fn<typeof efmvApi.updateEfmvAnalysis>(),
  deleteEfmvAnalysis: vi.fn<typeof efmvApi.deleteEfmvAnalysis>(),
  previewScenario: vi.fn<typeof efmvApi.previewScenario>(),
}))
vi.mock('@/modules/customers/api', () => ({
  listCustomers: vi.fn<typeof customersApi.listCustomers>(),
}))
vi.mock('@/modules/account-managers/api', () => ({
  listAccountManagers: vi.fn<typeof managersApi.listAccountManagers>(),
}))
vi.mock('@/modules/average-prices/api', () => ({
  listAveragePrices: vi.fn<typeof pricesApi.listAveragePrices>(),
}))

const efmv = vi.mocked(efmvApi)
const customers = vi.mocked(customersApi)
const managers = vi.mocked(managersApi)
const prices = vi.mocked(pricesApi)

const page = <T>(results: T[]) => ({ count: results.length, next: null, previous: null, results })
// The scenario asks the API for its figures after a short pause
const debounce = () => new Promise((r) => setTimeout(r, 400)).then(settle)

const EXCAVATOR: efmvApi.ScenarioItem = {
  id: 1,
  quantity: 2,
  available: true,
  average_price: 7,
  asset_class: { name: 'Excavators', icon: 'mdi-excavator' },
  manufacturer: 'Caterpillar',
  model: '320 GC',
  sub_vertical: 'Industry / Yellow line',
  original_value: '100000.00',
  currency: 'BRL',
  terms: [12, 24, 36],
  line_total: '200000.00',
  out_of_curve: false,
}

const TOTALS: efmvApi.ScenarioTotals = {
  lo: '200000.00',
  efmv_percent: null,
  hw_percent: '100.00',
  sw_percent: '0.00',
  sv_percent: '0.00',
}

const ANALYSIS: efmvApi.EfmvAnalysis = {
  id: 3,
  code: 'EFMV-2026-0003',
  account_manager: 10,
  account_manager_detail: { id: 10, full_name: 'Ana Lima' },
  customer: 20,
  customer_detail: { id: 20, name: 'Acme Ltda', trade_name: '', tax_id: '11222333000181' },
  scenarios: [
    { id: 1, name: 'Base', term_months: 36, scope: 'Fleet', items: [EXCAVATOR], totals: TOTALS },
  ],
  created_at: '2026-11-20T10:00:00Z',
  created_by_name: 'Fernando Almeida',
  updated_at: '2026-11-20T10:00:00Z',
}

async function mountView(props: { id?: number } = {}, roles = ['Account Manager']) {
  const pinia = createPinia()
  setActivePinia(pinia)
  useAuthStore().user = {
    id: 10,
    username: 'ana',
    name: 'Ana Lima',
    is_admin: false,
    roles,
    photo_version: null,
    preferences: {
      language: 'en',
      theme: 'light',
      color_theme: 'metallic_foundations',
      updated_at: '',
    },
  }
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/', name: 'efmv-analyses-list', component: { render: () => null } },
      { path: '/new', name: 'efmv-analysis-new', component: { render: () => null } },
      { path: '/:id', name: 'efmv-analysis', component: { render: () => null } },
    ],
  })
  await router.push(props.id ? `/${props.id}` : '/new')
  const replace = vi.spyOn(router, 'replace')
  const wrapper = mount(EfmvAnalysisView, {
    props,
    attachTo: document.body,
    global: { plugins: [vuetify, i18n, pinia, router] },
  })
  await settle()
  return { wrapper, replace }
}

describe('EfmvAnalysisView', () => {
  beforeEach(() => {
    setLanguage('en')
    customers.listCustomers.mockResolvedValue(
      page([{ id: 20, name: 'Acme Ltda', trade_name: '' } as customersApi.Customer]),
    )
    managers.listAccountManagers.mockResolvedValue(page([]))
    prices.listAveragePrices.mockResolvedValue(
      page([
        {
          id: 7,
          model: '320 GC',
          manufacturer: { id: 1, name: 'Caterpillar' },
          asset_class: { id: 5, name: 'Excavators', icon: 'mdi-excavator' },
        } as pricesApi.AveragePrice,
      ]),
    )
    efmv.previewScenario.mockResolvedValue({ items: [{ ...EXCAVATOR, id: null }], totals: TOTALS })
  })
  afterEach(() => {
    vi.clearAllMocks()
    document.body.innerHTML = ''
  })

  it('creates an analysis: the account manager is the user, customers are theirs', async () => {
    const { wrapper, replace } = await mountView()
    expect(inBody('[data-testid="analysis-title"]')!.textContent).toContain('New eFMV Analysis')
    // Only the customers this account manager serves are offered
    await pickOption('customer', 'Acme Ltda')
    expect(customers.listCustomers).toHaveBeenCalledWith(
      expect.objectContaining({ filters: { account_manager: 10, is_active: true } }),
    )
    await typeInto('scenario-name', 'Base')
    await typeInto('scenario-term', '36')
    await pickOption('add-asset', 'Caterpillar 320 GC · Excavators')
    await debounce()
    expect(efmv.previewScenario).toHaveBeenLastCalledWith({
      term_months: 36,
      items: [{ average_price: 7, quantity: 1 }],
    })
    expect(inBody('[data-testid="asset-row"]')!.textContent).toContain('Caterpillar 320 GC')
    expect(inBody('[data-testid="total-lo"]')!.textContent).toMatch(/200,000\.00/)
    expect(inBody('[data-testid="total-efmv"]')!.textContent).toContain('—')
    expect(inBody('[data-testid="total-hw"]')!.textContent).toContain('100.00%')

    efmv.createEfmvAnalysis.mockResolvedValue({ ...ANALYSIS, id: 4, code: 'EFMV-2026-0004' })
    await click('save')
    expect(efmv.createEfmvAnalysis).toHaveBeenCalledWith({
      account_manager: 10,
      customer: 20,
      scenarios: [
        { name: 'Base', term_months: 36, scope: '', items: [{ average_price: 7, quantity: 1 }] },
      ],
    })
    expect(replace).toHaveBeenCalledWith({ name: 'efmv-analysis', params: { id: 4 } })
    wrapper.unmount()
  })

  it('without the Account Manager role the customer waits for an account manager', async () => {
    const { wrapper } = await mountView({}, ['Administrator'])
    expect(inBody('[data-testid="customer-disabled"]')).not.toBeNull()
    await click('save')
    expect(efmv.createEfmvAnalysis).not.toHaveBeenCalled()
    wrapper.unmount()
  })

  it('opens an analysis with its figures and keeps at least one scenario', async () => {
    efmv.getEfmvAnalysis.mockResolvedValue(ANALYSIS)
    const { wrapper } = await mountView({ id: 3 })
    expect(inBody('[data-testid="analysis-title"]')!.textContent).toContain('EFMV-2026-0003')
    expect((inBody('[data-testid="created-at"] input') as HTMLInputElement).value).toBe(
      '11/20/2026',
    )
    expect(inBody('[data-testid="tab-0"]')!.textContent).toContain('Base')
    expect(inBody('[data-testid="total-lo"]')!.textContent).toMatch(/200,000\.00/)
    expect(inBody('[data-testid="remove-scenario"]')!.hasAttribute('disabled')).toBe(true)

    await click('duplicate-scenario')
    // The copy gets its own tab, next to the original, and opens
    expect(inBody('[data-testid="tab-1"]')!.textContent).toContain('Base (copy)')
    expect(inBody('[data-testid="tab-1"]')!.className).toContain('v-tab--selected')
    expect(inBody('[data-testid="remove-scenario"]')!.hasAttribute('disabled')).toBe(false)
    wrapper.unmount()
  })

  it('adds a scenario in a new tab; an invalid one is opened when saving', async () => {
    efmv.getEfmvAnalysis.mockResolvedValue(ANALYSIS)
    const { wrapper } = await mountView({ id: 3 })
    await click('add-scenario')
    expect(inBody('[data-testid="tab-1"]')!.textContent).toContain('Scenario 2')
    expect(inBody('[data-testid="tab-1"]')!.className).toContain('v-tab--selected')
    // Back to the first tab; the second gets an invalid term
    await click('tab-0')
    const term = document.querySelectorAll<HTMLInputElement>(
      '[data-testid="scenario-term"] input',
    )[1]!
    term.value = '0'
    term.dispatchEvent(new Event('input'))
    await settle()
    expect(inBody('[data-testid="tab-1"] [data-testid="tab-issue"]')).not.toBeNull()
    await click('save')
    expect(efmv.updateEfmvAnalysis).not.toHaveBeenCalled()
    expect(inBody('[data-testid="tab-1"]')!.className).toContain('v-tab--selected')
    wrapper.unmount()
  })

  it('shows what the server refuses next to the asset', async () => {
    efmv.getEfmvAnalysis.mockResolvedValue(ANALYSIS)
    const { wrapper } = await mountView({ id: 3 })
    efmv.updateEfmvAnalysis.mockRejectedValue(
      new ApiError(400, 'Bad Request', {
        scenarios: {
          '0': { items: { '0': { average_price: ['The value curve goes up to 24 months.'] } } },
        },
      }),
    )
    await click('save')
    expect(efmv.updateEfmvAnalysis).toHaveBeenCalled()
    expect(inBody('[data-testid="form-error"]')!.textContent).toContain('fix the fields')
    expect(inBody('[data-testid="asset-row"]')!.textContent).toContain('goes up to 24 months')
    expect(inBody('[data-testid="tab-0"] [data-testid="tab-issue"]')).not.toBeNull()
    wrapper.unmount()
  })

  it('flags assets whose curve does not reach the term', async () => {
    efmv.getEfmvAnalysis.mockResolvedValue(ANALYSIS)
    const { wrapper } = await mountView({ id: 3 })
    efmv.previewScenario.mockResolvedValue({
      items: [{ ...EXCAVATOR, out_of_curve: true, line_total: '200000.00' }],
      totals: { ...TOTALS, lo: '0.00', hw_percent: null, sw_percent: null, sv_percent: null },
    })
    await typeInto('scenario-term', '48')
    await debounce()
    expect(inBody('[data-testid="out-of-curve"]')!.textContent).toContain('48 months')
    expect(inBody('[data-testid="total-hw"]')!.textContent).toContain('—')
    wrapper.unmount()
  })
})
