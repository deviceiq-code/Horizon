import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createMemoryHistory, createRouter } from 'vue-router'

import { ApiError } from '@/api'
import { i18n, setLanguage } from '@/i18n'
import * as managersApi from '@/modules/account-managers/api'
import * as pricesApi from '@/modules/average-prices/api'
import * as verticalsApi from '@/modules/catalogs/verticals/api'
import * as customersApi from '@/modules/customers/api'
import vuetify from '@/plugins/vuetify'
import { useAuthStore } from '@/stores/auth'
import { click, inBody, openDropdown, pickOption, settle, typeInto } from '@/test-utils'
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
vi.mock('@/modules/catalogs/verticals/api', () => ({
  listSubVerticals: vi.fn<typeof verticalsApi.listSubVerticals>(),
}))
vi.mock('@/modules/average-prices/api', () => ({
  listAveragePrices: vi.fn<typeof pricesApi.listAveragePrices>(),
}))

const efmv = vi.mocked(efmvApi)
const customers = vi.mocked(customersApi)
const managers = vi.mocked(managersApi)
const prices = vi.mocked(pricesApi)
const verticals = vi.mocked(verticalsApi)

const dropdownSubtitles = () =>
  [...document.querySelectorAll('.v-overlay--active .v-list-item-subtitle')].map((el) =>
    el.textContent?.trim(),
  )

const page = <T>(results: T[]) => ({ count: results.length, next: null, previous: null, results })
// The scenario asks the API for its figures after a short pause
const debounce = () => new Promise((r) => setTimeout(r, 400)).then(settle)

const EXCAVATOR: efmvApi.ScenarioItem = {
  id: 1,
  quantity: 2,
  unit_value: '100000.00',
  available: true,
  average_price: 7,
  asset_class: { name: 'Excavators', icon: 'mdi-excavator' },
  manufacturer: 'Caterpillar',
  model: '320 GC',
  specs: [
    {
      key: 'hours',
      label: 'Hours',
      kind: 'number',
      unit: 'h',
      required: true,
      options: [],
      value: '2500',
    },
    {
      key: 'cab',
      label: 'Cab',
      kind: 'boolean',
      unit: '',
      required: false,
      options: [],
      value: 'true',
    },
  ],
  sub_vertical: 'Industry / Yellow line',
  original_value: '100000.00',
  currency: 'BRL',
  terms: [12, 24, 36],
  line_total: '200000.00',
  out_of_curve: false,
  priced_on: '2026-10-01',
  valid_until: '2027-10-01',
  expired: false,
  variation_percent: '0.00',
  position: 'compatible',
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
  is_outdated: false,
  scenarios: [
    {
      id: 1,
      name: 'Base',
      term_months: 36,
      scope: 'Fleet',
      vertical: 1,
      sub_vertical: null,
      scope_label: 'Industry',
      items: [EXCAVATOR],
      totals: TOTALS,
      has_expired: false,
    },
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
    verticals.listSubVerticals.mockResolvedValue(
      page([
        {
          id: 10,
          name: 'General',
          is_general: true,
          label: 'Industry / General',
          vertical: { id: 1, name: 'Industry', is_enabled: true },
          allowed_terms: [36],
          recommended_term: 36,
        },
        {
          id: 11,
          name: 'Yellow line',
          is_general: false,
          label: 'Industry / Yellow line',
          vertical: { id: 1, name: 'Industry', is_enabled: true },
          allowed_terms: [36],
          recommended_term: 36,
        },
      ]),
    )
    prices.listAveragePrices.mockResolvedValue(
      page([
        {
          id: 7,
          model: '320 GC',
          manufacturer: { id: 1, name: 'Caterpillar' },
          asset_class: { id: 5, name: 'Excavators', icon: 'mdi-excavator' },
          specs: [
            {
              key: 'hours',
              label: 'Hours',
              kind: 'number',
              unit: 'h',
              required: true,
              options: [],
              value: '2500',
            },
            {
              key: 'cab',
              label: 'Cab',
              kind: 'boolean',
              unit: '',
              required: false,
              options: [],
              value: 'true',
            },
            {
              key: 'tracks',
              label: 'Tracks',
              kind: 'text',
              unit: '',
              required: false,
              options: [],
              value: '',
            },
          ],
        } as unknown as pricesApi.AveragePrice,
      ]),
    )
    efmv.previewScenario.mockResolvedValue({
      items: [{ ...EXCAVATOR, id: null }],
      totals: TOTALS,
      has_expired: false,
    })
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
    // The vertical comes first: it limits the assets offered
    expect(inBody('[data-testid="add-row"]')!.hasAttribute('disabled')).toBe(true)
    await pickOption('scenario-vertical', 'Yellow line')
    // "+ Row" adds an empty row; the asset is chosen in it
    await click('add-row')
    expect(inBody('[data-testid="quantity"] input')!.hasAttribute('disabled')).toBe(true)
    await openDropdown('add-asset')
    expect(dropdownSubtitles()).toEqual(['Caterpillar · Excavators'])
    await pickOption('add-asset', '320 GC (2500 h, Cab: Yes)')
    expect(prices.listAveragePrices).toHaveBeenLastCalledWith(
      expect.objectContaining({ filters: { vertical: 1, sub_vertical: 11 } }),
    )
    expect(inBody('[data-testid="add-asset"]')).toBeNull()
    // The value is not taken from Average Prices: the analyst types it
    expect((inBody('[data-testid="unit-value"] input') as HTMLInputElement).value).toBe('')
    await typeInto('unit-value', '100,000')
    await debounce()
    expect(efmv.previewScenario).toHaveBeenLastCalledWith({
      term_months: 36,
      vertical: 1,
      sub_vertical: 11,
      items: [{ average_price: 7, quantity: 1, unit_value: '100000' }],
    })
    expect(inBody('[data-testid="position"]')!.textContent).toContain('Compatible')
    expect(inBody('[data-testid="asset-row"]')!.textContent).toContain('320 GC · Caterpillar')
    // Under it: asset class, specifications and the date of the price
    expect(inBody('[data-testid="asset-row"]')!.textContent!.replace(/\s+/g, ' ')).toMatch(
      /Excavators · 2500 h, Cab: Yes · priced on 10\/0?1\/2026/,
    )
    expect(inBody('[data-testid="total-lo"]')!.textContent).toMatch(/200,000\.00/)
    expect(inBody('[data-testid="total-efmv"]')!.textContent).toContain('—')
    expect(inBody('[data-testid="total-hw"]')!.textContent).toContain('100.00%')

    efmv.createEfmvAnalysis.mockResolvedValue({ ...ANALYSIS, id: 4, code: 'EFMV-2026-0004' })
    await click('save')
    expect(efmv.createEfmvAnalysis).toHaveBeenCalledWith({
      account_manager: 10,
      customer: 20,
      scenarios: [
        {
          name: 'Base',
          term_months: 36,
          scope: '',
          vertical: 1,
          sub_vertical: 11,
          items: [{ average_price: 7, quantity: 1, unit_value: '100000' }],
        },
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

  it('the quantity comes first; the value typed is placed against Average Prices', async () => {
    efmv.getEfmvAnalysis.mockResolvedValue(ANALYSIS)
    const { wrapper } = await mountView({ id: 3 })
    const titles = [...document.querySelectorAll('[data-testid="assets"] th')].map((th) =>
      th.textContent?.trim(),
    )
    // After the row number
    expect(titles.slice(0, 2)).toEqual(['#', 'Quantity'])
    expect((inBody('[data-testid="unit-value"] input') as HTMLInputElement).value).toBe(
      '100,000.00',
    )
    efmv.previewScenario.mockResolvedValue({
      items: [
        { ...EXCAVATOR, unit_value: '88000.00', variation_percent: '-12.00', position: 'below' },
      ],
      totals: TOTALS,
      has_expired: false,
    })
    await typeInto('unit-value', '88000')
    await debounce()
    expect(inBody('[data-testid="position"]')!.textContent).toMatch(/Below Historical.*-12\.00%/)
    wrapper.unmount()
  })

  it('an expired average price marks the analysis as possibly outdated', async () => {
    const expired = {
      ...EXCAVATOR,
      expired: true,
      priced_on: '2025-01-10',
      valid_until: '2026-01-10',
    }
    efmv.getEfmvAnalysis.mockResolvedValue({
      ...ANALYSIS,
      is_outdated: true,
      scenarios: [{ ...ANALYSIS.scenarios[0]!, items: [expired], has_expired: true }],
    })
    const { wrapper } = await mountView({ id: 3 })
    expect(inBody('[data-testid="outdated"]')!.textContent).toContain('Possibly Outdated')
    expect(inBody('[data-testid="expired"]')!.textContent).toContain('Expired Price')
    expect(inBody('[data-testid="expired-warning"]')).not.toBeNull()
    expect(inBody('[data-testid="tab-0"] [data-testid="tab-expired"]')).not.toBeNull()
    wrapper.unmount()
  })

  it('Enter moves down the same column; on the last row it adds a row', async () => {
    efmv.getEfmvAnalysis.mockResolvedValue({
      ...ANALYSIS,
      scenarios: [
        {
          ...ANALYSIS.scenarios[0]!,
          items: [EXCAVATOR, { ...EXCAVATOR, id: 2, average_price: 8, unit_value: '5.00' }],
        },
      ],
    })
    const { wrapper } = await mountView({ id: 3 })
    const units = document.querySelectorAll<HTMLInputElement>('[data-testid="unit-value"] input')
    units[0]!.focus()
    units[0]!.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', bubbles: true }))
    await settle()
    expect(document.activeElement).toBe(units[1])
    units[1]!.dispatchEvent(new KeyboardEvent('keydown', { key: 'ArrowUp', bubbles: true }))
    await settle()
    expect(document.activeElement).toBe(units[0])
    units[1]!.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', bubbles: true }))
    await settle()
    expect(document.querySelectorAll('[data-testid="asset-row"]')).toHaveLength(3)
    expect(inBody('[data-testid="add-asset"]')).not.toBeNull()
    wrapper.unmount()
  })

  it("without a typed value the average price's value counts (placeholder)", async () => {
    efmv.getEfmvAnalysis.mockResolvedValue(ANALYSIS)
    efmv.updateEfmvAnalysis.mockResolvedValue(ANALYSIS)
    efmv.previewScenario.mockResolvedValue({
      items: [{ ...EXCAVATOR, value_from_price: true }],
      totals: TOTALS,
      has_expired: false,
    })
    const { wrapper } = await mountView({ id: 3 })
    await typeInto('unit-value', '')
    await debounce()
    const input = inBody('[data-testid="unit-value"] input') as HTMLInputElement
    expect(input.placeholder).toBe('100,000.00')
    expect(efmv.previewScenario).toHaveBeenLastCalledWith({
      term_months: 36,
      vertical: 1,
      sub_vertical: null,
      items: [{ average_price: 7, quantity: 2, unit_value: null }],
    })
    await click('save')
    expect(efmv.updateEfmvAnalysis).toHaveBeenCalledWith(
      3,
      expect.objectContaining({
        scenarios: [
          expect.objectContaining({ items: [{ average_price: 7, quantity: 2, unit_value: null }] }),
        ],
      }),
    )
    wrapper.unmount()
  })

  it('an empty row is left out when saving', async () => {
    efmv.getEfmvAnalysis.mockResolvedValue(ANALYSIS)
    efmv.updateEfmvAnalysis.mockResolvedValue(ANALYSIS)
    const { wrapper } = await mountView({ id: 3 })
    await click('add-row')
    expect(document.querySelectorAll('[data-testid="asset-row"]')).toHaveLength(2)
    await click('save')
    expect(efmv.updateEfmvAnalysis).toHaveBeenCalledWith(3, {
      account_manager: 10,
      customer: 20,
      scenarios: [
        {
          name: 'Base',
          term_months: 36,
          scope: 'Fleet',
          vertical: 1,
          sub_vertical: null,
          items: [{ average_price: 7, quantity: 2, unit_value: '100000.00' }],
        },
      ],
    })
    wrapper.unmount()
  })

  it('assets outside the vertical are flagged and mark the tab', async () => {
    efmv.getEfmvAnalysis.mockResolvedValue(ANALYSIS)
    const { wrapper } = await mountView({ id: 3 })
    efmv.previewScenario.mockResolvedValue({
      items: [{ ...EXCAVATOR, out_of_scope: true }],
      totals: { ...TOTALS, lo: '0.00', hw_percent: null, sw_percent: null, sv_percent: null },
      has_expired: false,
    })
    await pickOption('scenario-vertical', 'Yellow line')
    await debounce()
    expect(efmv.previewScenario).toHaveBeenLastCalledWith(
      expect.objectContaining({ vertical: 1, sub_vertical: 11 }),
    )
    expect(inBody('[data-testid="out-of-scope"]')!.textContent).toContain("scenario's vertical")
    expect(inBody('[data-testid="tab-0"] [data-testid="tab-issue"]')).not.toBeNull()
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
      has_expired: false,
    })
    await typeInto('scenario-term', '48')
    await debounce()
    expect(inBody('[data-testid="out-of-curve"]')!.textContent).toContain('48 months')
    expect(inBody('[data-testid="total-hw"]')!.textContent).toContain('—')
    wrapper.unmount()
  })
})
