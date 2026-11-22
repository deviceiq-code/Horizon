import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createMemoryHistory, createRouter } from 'vue-router'

import { ApiError } from '@/api'
import { i18n, setLanguage } from '@/i18n'
import * as pricesApi from '@/modules/average-prices/api'
import vuetify from '@/plugins/vuetify'
import { useAuthStore } from '@/stores/auth'
import { click, inBody, openDropdown, pickOption, settle, typeInto } from '@/test-utils'
import * as efmvApi from '../api'
import EfmvAnalysisView from '../EfmvAnalysisView.vue'

vi.mock('../api', () => ({
  getEfmvAnalysis: vi.fn<typeof efmvApi.getEfmvAnalysis>(),
  getAccountManagerSummary: vi.fn<typeof efmvApi.getAccountManagerSummary>(),
  updateEfmvAnalysis: vi.fn<typeof efmvApi.updateEfmvAnalysis>(),
  deleteEfmvAnalysis: vi.fn<typeof efmvApi.deleteEfmvAnalysis>(),
  previewScenario: vi.fn<typeof efmvApi.previewScenario>(),
}))
vi.mock('@/modules/average-prices/api', () => ({
  listAveragePrices: vi.fn<typeof pricesApi.listAveragePrices>(),
}))

const efmv = vi.mocked(efmvApi)
const prices = vi.mocked(pricesApi)

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
  efmv_value: '42500.00',
  curve_value: '42500.00',
  efmv_from_curve: true,
  efmv_percent: '42.50',
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
  weight_percent: '100.00',
  out_of_curve: false,
  priced_on: '2026-10-01',
  valid_until: '2027-10-01',
  expired: false,
  variation_percent: '0.00',
  position: 'compatible',
}

const TOTALS: efmvApi.ScenarioTotals = {
  lo: '200000.00',
  efmv_total: '85000.00',
  efmv_percent: '42.50',
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
  vertical: 1,
  sub_vertical: null,
  vertical_label: 'Industry',
  is_outdated: false,
  scenarios: [
    {
      id: 1,
      name: 'Base',
      title: '36 Months - Base',
      term_months: 36,
      scope: 'Fleet',
      items: [EXCAVATOR],
      totals: TOTALS,
      has_expired: false,
    },
  ],
  created_at: '2026-11-20T10:00:00Z',
  created_by_name: 'Fernando Almeida',
  updated_at: '2026-11-20T10:00:00Z',
}

async function mountView(props: { id: number } = { id: 3 }, roles = ['Account Manager']) {
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
      ui_scale: 'auto',
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
  await router.push(`/${props.id}`)
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
    efmv.getAccountManagerSummary.mockResolvedValue({
      id: 10,
      full_name: 'Ana Lima',
      email: 'ana@example.com',
      job_title: '',
      photo_version: 'p1',
      verticals: [],
      analyses_count: 1,
      top_verticals: [],
      primary_customers_count: 1,
    })
  })
  afterEach(() => {
    vi.clearAllMocks()
    document.body.innerHTML = ''
  })

  it("adds an asset in a row: only the analysis's vertical is offered", async () => {
    efmv.getEfmvAnalysis.mockResolvedValue({
      ...ANALYSIS,
      sub_vertical: 11,
      vertical_label: 'Industry / Yellow line',
      scenarios: [{ ...ANALYSIS.scenarios[0]!, items: [] }],
    })
    efmv.updateEfmvAnalysis.mockResolvedValue(ANALYSIS)
    const { wrapper } = await mountView()
    // The premises are labels (set by the wizard)
    expect(inBody('[data-testid="premise-account-manager"]')!.textContent).toContain('Ana Lima')
    expect(inBody('[data-testid="premise-customer"]')!.textContent).toContain('Acme Ltda')
    expect(inBody('[data-testid="premise-vertical"]')!.textContent).toContain(
      'Industry / Yellow line',
    )
    expect(inBody('[data-testid="account-manager"]')).toBeNull()
    // Analyses are deleted from the list's grid, not here
    expect(inBody('[data-testid="delete"]')).toBeNull()
    // The scenario shows the vertical; its assets are of it
    expect(inBody('[data-testid="scenario-vertical"]')!.textContent).toContain(
      'Industry / Yellow line',
    )
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
      items: [{ average_price: 7, quantity: 1, unit_value: '100000', efmv_value: null }],
    })
    expect(inBody('[data-testid="position"]')!.textContent).toContain('Compatible')
    expect(inBody('[data-testid="asset-row"]')!.textContent).toContain('320 GC · Caterpillar')
    // Under it: asset class, specifications and the date of the price
    expect(inBody('[data-testid="asset-row"]')!.textContent!.replace(/\s+/g, ' ')).toMatch(
      /Excavators · 2500 h, Cab: Yes · priced on 10\/0?1\/2026/,
    )
    expect(inBody('[data-testid="total-lo"]')!.textContent).toMatch(/200,000\.00/)
    // The eFMV of the assets weighted over the LO, and what they are worth at the end
    expect(inBody('[data-testid="total-efmv"]')!.textContent).toMatch(
      /42\.50%\s*· R\$\s?85,000\.00/,
    )
    expect(inBody('[data-testid="total-hw"]')!.textContent).toContain('100.00%')
    // Below the row's total: its share of the scenario's LO (no column of its own)
    const headers = [...document.querySelectorAll('[data-testid="assets"] th')].map((th) =>
      th.textContent?.trim(),
    )
    expect(headers.filter(Boolean).pop()).toBe('Total')
    expect(inBody('[data-testid="weight"]')!.textContent?.trim()).toBe('Weight (100.00%)')

    // Saving sends only the scenarios (the premises do not change)
    await click('save')
    expect(efmv.updateEfmvAnalysis).toHaveBeenCalledWith(3, {
      scenarios: [
        {
          name: 'Base',
          term_months: 36,
          scope: 'Fleet',
          items: [{ average_price: 7, quantity: 1, unit_value: '100000', efmv_value: null }],
        },
      ],
    })
    wrapper.unmount()
  })

  it('opens an analysis with its figures and keeps at least one scenario', async () => {
    efmv.getEfmvAnalysis.mockResolvedValue(ANALYSIS)
    const { wrapper } = await mountView({ id: 3 })
    expect(inBody('[data-testid="analysis-title"]')!.textContent).toContain('EFMV-2026-0003')
    expect(inBody('[data-testid="created-at"]')!.textContent).toMatch(/11\/20\/2026/)
    expect(inBody('[data-testid="tab-0"]')!.textContent).toContain('Base')
    expect(inBody('[data-testid="total-lo"]')!.textContent).toMatch(/200,000\.00/)
    expect(inBody('[data-testid="remove-scenario"]')!.hasAttribute('disabled')).toBe(true)

    await click('duplicate-scenario')
    // The copy gets its own tab, next to the original, and opens
    expect(inBody('[data-testid="tab-1"]')!.textContent).toContain('Base (copy)')
    expect(inBody('[data-testid="tab-1"]')!.className).toContain('v-tab--selected')
    expect(inBody('[data-testid="remove-scenario"]')!.hasAttribute('disabled')).toBe(false)
    // Add, duplicate and remove sit together in the toolbar of the tabs
    const toolbar = inBody('[data-testid="scenario-toolbar"]')!
    for (const id of ['add-scenario', 'duplicate-scenario', 'remove-scenario']) {
      expect(toolbar.querySelector(`[data-testid="${id}"]`)).not.toBeNull()
    }
    // Short names on the buttons; the full ones in the tooltips
    expect(
      ['add-scenario', 'duplicate-scenario', 'remove-scenario'].map((id) =>
        toolbar.querySelector(`[data-testid="${id}"]`)!.textContent!.trim(),
      ),
    ).toEqual(['Add New', 'Duplicate', 'Remove'])
    expect(inBody('[data-testid="duplicate-scenario"]')!.getAttribute('title')).toBe(
      'Duplicate Scenario',
    )
    // Remove acts on the open scenario (the copy)
    await click('remove-scenario')
    expect(inBody('.v-overlay--active')!.textContent).toContain('Base (copy)')
    await click('confirm-button')
    expect(document.querySelectorAll('[data-testid^="tab-"]').length).toBeGreaterThan(0)
    expect(inBody('[data-testid="tab-1"]')).toBeNull()
    expect(inBody('[data-testid="tab-0"]')!.textContent).toContain('Base')
    wrapper.unmount()
  })

  it('adds a scenario in a new tab; an invalid one is opened when saving', async () => {
    efmv.getEfmvAnalysis.mockResolvedValue(ANALYSIS)
    const { wrapper } = await mountView({ id: 3 })
    await click('add-scenario')
    // The official name is the term + the name; a new scenario has no name
    expect(inBody('[data-testid="tab-0"]')!.textContent!.trim()).toBe('36 Months - Base')
    expect(inBody('[data-testid="tab-1"]')!.textContent!.trim()).toBe('36 Months')
    expect(inBody('[data-testid="tab-1"]')!.className).toContain('v-tab--selected')
    // Another one at 36 months would repeat "36 Months": it gets a name
    await click('add-scenario')
    expect(inBody('[data-testid="tab-2"]')!.textContent!.trim()).toBe('36 Months - Scenario 3')
    // The tab follows the term and the name as they are typed
    const names = () =>
      document.querySelectorAll<HTMLInputElement>('[data-testid="scenario-name"] input')
    names()[2]!.value = ''
    names()[2]!.dispatchEvent(new Event('input'))
    await settle()
    const nameTaken = () =>
      document
        .querySelectorAll('[data-testid="scenario-name"]')[2]!
        .className.includes('v-input--error')
    expect(nameTaken()).toBe(true)
    const terms = () =>
      document.querySelectorAll<HTMLInputElement>('[data-testid="scenario-term"] input')
    terms()[2]!.value = '60'
    terms()[2]!.dispatchEvent(new Event('input'))
    await settle()
    expect(inBody('[data-testid="tab-2"]')!.textContent!.trim()).toBe('60 Months')
    // Tabs in the order of the official names: term (as a number), then name
    const tabs = () =>
      [...document.querySelectorAll('[data-testid^="tab-"]')]
        .filter((el) => /^tab-\d+$/.test((el as HTMLElement).dataset.testid!))
        .map((el) => el.textContent!.trim())
    expect(tabs()).toEqual(['36 Months', '36 Months - Base', '60 Months'])
    terms()[2]!.value = '120'
    terms()[2]!.dispatchEvent(new Event('input'))
    terms()[1]!.value = '12'
    terms()[1]!.dispatchEvent(new Event('input'))
    await settle()
    expect(tabs()).toEqual(['12 Months', '36 Months - Base', '120 Months'])
    expect(nameTaken()).toBe(false)
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
    // An asset already in the scenario can be added again (e.g. another delivery state)
    await openDropdown('add-asset')
    expect(document.querySelector('.v-overlay--active')!.textContent).toContain('320 GC')
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
      items: [{ average_price: 7, quantity: 2, unit_value: null, efmv_value: null }],
    })
    await click('save')
    expect(efmv.updateEfmvAnalysis).toHaveBeenCalledWith(
      3,
      expect.objectContaining({
        scenarios: [
          expect.objectContaining({
            items: [{ average_price: 7, quantity: 2, unit_value: null, efmv_value: null }],
          }),
        ],
      }),
    )
    wrapper.unmount()
  })

  it('the eFMV value comes from the curve at the term (placeholder) or is typed', async () => {
    efmv.getEfmvAnalysis.mockResolvedValue({
      ...ANALYSIS,
      scenarios: [
        {
          ...ANALYSIS.scenarios[0]!,
          items: [{ ...EXCAVATOR, efmv_value: '40000.00', efmv_from_curve: false }],
        },
      ],
    })
    efmv.previewScenario.mockResolvedValue({
      items: [{ ...EXCAVATOR, efmv_value: '41000.00', efmv_from_curve: false }],
      totals: TOTALS,
      has_expired: false,
    })
    const { wrapper } = await mountView({ id: 3 })
    const input = () => inBody('[data-testid="efmv-value"] input') as HTMLInputElement
    // Typed before: shown as typed; the curve's value stays as the placeholder
    expect(input().value).toBe('40,000.00')
    expect(input().placeholder).toBe('42,500.00')
    await typeInto('efmv-value', '41000')
    await debounce()
    expect(efmv.previewScenario).toHaveBeenLastCalledWith(
      expect.objectContaining({
        items: [{ average_price: 7, quantity: 2, unit_value: '100000.00', efmv_value: '41000' }],
      }),
    )
    // Emptied: the curve counts
    await typeInto('efmv-value', '')
    await debounce()
    expect(efmv.previewScenario).toHaveBeenLastCalledWith(
      expect.objectContaining({
        items: [{ average_price: 7, quantity: 2, unit_value: '100000.00', efmv_value: null }],
      }),
    )
    // Below the field: the eFMV as a percentage of the unit value
    expect(inBody('[data-testid="efmv-percent"]')!.textContent).toContain('% Value (42.50%)')
    // A percentage of the unit value is turned into its value when the cell is left
    efmv.previewScenario.mockResolvedValue({
      items: [
        { ...EXCAVATOR, efmv_value: '25000.00', efmv_percent: '25.00', efmv_from_curve: false },
      ],
      totals: TOTALS,
      has_expired: false,
    })
    await typeInto('efmv-value', '25%')
    input().dispatchEvent(new Event('blur'))
    await settle()
    expect(efmv.previewScenario).toHaveBeenLastCalledWith(
      expect.objectContaining({
        items: [
          {
            average_price: 7,
            quantity: 2,
            unit_value: '100000.00',
            efmv_value: null,
            efmv_percent: '25',
          },
        ],
      }),
    )
    expect(input().value).toBe('25,000.00')
    expect(inBody('[data-testid="efmv-percent"]')!.textContent!.trim()).toBe('% Value (25.00%)')
    // Negative: a disposal cost
    await typeInto('efmv-value', '-5')
    await debounce()
    expect(efmv.previewScenario).toHaveBeenLastCalledWith(
      expect.objectContaining({
        items: [{ average_price: 7, quantity: 2, unit_value: '100000.00', efmv_value: '-5' }],
      }),
    )
    // What is not a value nor a percentage is refused before saving
    await typeInto('efmv-value', 'abc')
    await click('save')
    expect(efmv.updateEfmvAnalysis).not.toHaveBeenCalled()
    wrapper.unmount()
  })

  it('after saving, the open scenario is still shown', async () => {
    efmv.getEfmvAnalysis.mockResolvedValue(ANALYSIS)
    efmv.updateEfmvAnalysis.mockResolvedValue(ANALYSIS)
    const { wrapper } = await mountView({ id: 3 })
    const shown = () =>
      document.querySelector('.v-window-item--active [data-testid="scenario-0"]') !== null
    expect(shown()).toBe(true)
    await click('save')
    await settle()
    expect(efmv.updateEfmvAnalysis).toHaveBeenCalled()
    expect(shown()).toBe(true)
    expect(inBody('.v-tab--selected')!.textContent).toContain('Base')
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
      scenarios: [
        {
          name: 'Base',
          term_months: 36,
          scope: 'Fleet',
          items: [{ average_price: 7, quantity: 2, unit_value: '100000.00', efmv_value: null }],
        },
      ],
    })
    wrapper.unmount()
  })

  it('assets outside the vertical are flagged and mark the tab', async () => {
    efmv.getEfmvAnalysis.mockResolvedValue({ ...ANALYSIS, sub_vertical: 11 })
    efmv.previewScenario.mockResolvedValue({
      items: [{ ...EXCAVATOR, out_of_scope: true }],
      totals: {
        ...TOTALS,
        lo: '0.00',
        efmv_total: '0.00',
        efmv_percent: null,
        hw_percent: null,
        sw_percent: null,
        sv_percent: null,
      },
      has_expired: false,
    })
    const { wrapper } = await mountView({ id: 3 })
    // A change asks the API again, with the analysis's sub-vertical
    await typeInto('quantity', '3')
    await debounce()
    expect(efmv.previewScenario).toHaveBeenLastCalledWith(
      expect.objectContaining({ vertical: 1, sub_vertical: 11 }),
    )
    expect(inBody('[data-testid="out-of-scope"]')!.textContent).toContain("analysis's vertical")
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
      totals: {
        ...TOTALS,
        lo: '0.00',
        efmv_total: '0.00',
        efmv_percent: null,
        hw_percent: null,
        sw_percent: null,
        sv_percent: null,
      },
      has_expired: false,
    })
    await typeInto('scenario-term', '48')
    await debounce()
    expect(inBody('[data-testid="out-of-curve"]')!.textContent).toContain('48 months')
    expect(inBody('[data-testid="total-hw"]')!.textContent).toContain('—')
    wrapper.unmount()
  })
})
