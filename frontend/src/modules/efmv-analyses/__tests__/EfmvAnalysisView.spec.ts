import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createMemoryHistory, createRouter } from 'vue-router'

import { ApiError } from '@/api'
import { i18n, setLanguage } from '@/i18n'
import * as pricesApi from '@/modules/average-prices/api'
import vuetify from '@/plugins/vuetify'
import { useAuthStore } from '@/stores/auth'
import {
  click,
  inBody,
  openDropdown,
  pickOption,
  settle,
  typeInto,
  typeKeywords,
} from '@/test-utils'
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
  hw_total: '200000.00',
  sw_total: '0.00',
  sv_total: '0.00',
}

const ANALYSIS: efmvApi.EfmvAnalysis = {
  id: 3,
  keywords: [],
  external_reference: '',
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
      scope_suggestion: 'Caterpillar Excavators',
    },
  ],
  created_at: '2026-11-20T10:00:00Z',
  created_by_name: 'Fernando Almeida',
  updated_at: '2026-11-20T10:00:00Z',
}

async function mountView(
  props: { id: number; scenario?: number } = { id: 3 },
  roles = ['Account Manager'],
) {
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
      date_format: 'auto',
      time_format: 'auto',
      select_on_focus: true,
      word_dictionary: true,
      trim_spaces: true,
      journal_days: 7,
      auto_scope: true,
      scope_threshold: '5.00',
      number_format: 'auto',
      percent_places: 2,
      currency: 'BRL',
      currency_display: 'symbol',
      ui_state: {},
      user_name_display: 'full_name',
      full_name_order: 'first_last',
      searxng_url: '',
      web_search: true,
      web_search_engine: 'google',
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

/** "+ Row" is a menu: Hardware / Software / Service */
async function addRow(kind: 'hw' | 'sw' | 'sv' = 'hw') {
  await click('add-row')
  await click(`add-row-${kind}`)
}

/** "Attach" is a menu: Software / Service (for the selected hardware) */
async function attach(key: 'software' | 'service') {
  await click('attach')
  await click(`attach-${key}`)
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
    // "+ Row › Hardware" adds an empty row; the asset is chosen in it
    await addRow()
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
    // HW / SW / SV: the percentage and its value, as eFMV at EOL
    expect(inBody('[data-testid="hw-total"]')!.textContent).toMatch(/R\$\s?200,000\.00/)
    // Lined up with the scope: the shares sit beside it in the head
    expect(
      inBody('[data-testid="totals-shares"]')!.previousElementSibling!.getAttribute('data-testid'),
    ).toBe('scenario-scope')
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

  it('opens on the scenario asked for (clicked on the list); else on the first tab', async () => {
    const base = ANALYSIS.scenarios[0]!
    efmv.getEfmvAnalysis.mockResolvedValue({
      ...ANALYSIS,
      scenarios: [
        { ...base, id: 21, name: '', title: '36 Months' },
        { ...base, id: 22, name: '', title: '60 Months', term_months: 60 },
      ],
    })
    const { wrapper } = await mountView({ id: 3, scenario: 22 })
    expect(inBody('[data-testid="tab-1"]')!.textContent!.trim()).toBe('60 Months')
    expect(inBody('[data-testid="tab-1"]')!.className).toContain('v-tab--selected')
    wrapper.unmount()

    const { wrapper: first } = await mountView({ id: 3 })
    expect(inBody('[data-testid="tab-0"]')!.className).toContain('v-tab--selected')
    first.unmount()
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

  it('keywords change on their own (saved at once), keeping the scenarios being edited', async () => {
    efmv.getEfmvAnalysis.mockResolvedValue(ANALYSIS)
    efmv.updateEfmvAnalysis.mockResolvedValue({ ...ANALYSIS, keywords: ['renewal'] })
    const { wrapper } = await mountView({ id: 3 })
    expect(inBody('[data-testid="premise-keywords"]')!.textContent).toContain('—')
    await typeInto('scenario-name', 'Changed')
    await click('edit-keywords')
    await typeKeywords('Renewal')
    await click('save-keywords')
    await settle()
    expect(efmv.updateEfmvAnalysis).toHaveBeenCalledWith(3, { keywords: ['renewal'] })
    expect(inBody('[data-testid="keywords-text"]')!.textContent).toContain('renewal')
    // The unsaved scenario name stays
    const name = inBody('[data-testid="scenario-name"] input') as HTMLInputElement
    expect(name.value).toBe('Changed')
    wrapper.unmount()
  })

  it('the external reference changes on its own, saved at once', async () => {
    efmv.getEfmvAnalysis.mockResolvedValue(ANALYSIS)
    efmv.updateEfmvAnalysis.mockResolvedValue({ ...ANALYSIS, external_reference: 'CRM-12345' })
    const { wrapper } = await mountView({ id: 3 })
    expect(inBody('[data-testid="premise-reference"]')!.textContent).toContain('—')
    await click('edit-reference')
    await typeInto('reference', ' CRM-12345 ')
    await click('save-reference')
    await settle()
    expect(efmv.updateEfmvAnalysis).toHaveBeenCalledWith(3, { external_reference: 'CRM-12345' })
    expect(inBody('[data-testid="reference-text"]')!.textContent).toContain('CRM-12345')
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

  it('the selected asset gets a service (SV) row under it; services can be removed', async () => {
    efmv.getEfmvAnalysis.mockResolvedValue(ANALYSIS)
    efmv.updateEfmvAnalysis.mockResolvedValue(ANALYSIS)
    const { wrapper } = await mountView()
    // Nothing selected: nothing to act on
    expect(inBody('[data-testid="attach"]')!.hasAttribute('disabled')).toBe(true)
    expect(inBody('[data-testid="remove-selected"]')!.hasAttribute('disabled')).toBe(true)
    // A click selects the row (one at a time)
    await click('asset-row')
    expect(inBody('[data-testid="asset-row"]')!.className).toContain('row-selected')
    efmv.previewScenario.mockResolvedValue({
      items: [
        {
          ...EXCAVATOR,
          service: {
            name: 'Service',
            mode: 'add',
            value: '0.00',
            line_total: '0.00',
            weight_percent: '0.00',
            too_high: false,
          },
        },
      ],
      totals: TOTALS,
      has_expired: false,
    })
    await attach('service')
    // The service row: no name yet ("Service" shown), zero, added to the asset; only its
    // asset, value and total (no number, quantity nor eFMV)
    expect(document.querySelectorAll('[data-testid="service-row"]')).toHaveLength(1)
    const name = inBody('[data-testid="service-name"] input') as HTMLInputElement
    expect(name.placeholder).toBe('Service')
    expect(name.value).toBe('')
    expect((inBody('[data-testid="service-value"] input') as HTMLInputElement).value).toBe('0.00')
    expect(inBody('[data-testid="service-mode"]')!.textContent).toContain('Added to the asset')
    const serviceCells = [...inBody('[data-testid="service-row"]')!.querySelectorAll('td')]
    expect(serviceCells[0]!.textContent!.trim()).toBe('') // #
    expect(serviceCells[1]!.textContent!.trim()).toBe('') // quantity
    expect(serviceCells[4]!.textContent!.trim()).toBe('') // eFMV
    // Units counted apart: 2 assets (HW, the row's quantity) with their 2 services (SV)
    const count = (kind: string) =>
      inBody(`[data-testid="asset-count-${kind}"]`)!.textContent!.replace(/\s+/g, ' ').trim()
    expect([count('hw'), count('sw'), count('sv')]).toEqual(['HW 2', 'SW 0', 'SV 2'])
    // One service per asset: no second one (software still can be attached)
    await click('attach')
    expect(inBody('[data-testid="attach-service"]')!.className).toContain('v-list-item--disabled')
    expect(inBody('[data-testid="attach-software"]')!.className).not.toContain(
      'v-list-item--disabled',
    )
    document.body.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true }))
    await settle()

    // 8% deducted from the asset: the API resolves it
    await typeInto('service-value', '8%')
    await click('service-mode')
    expect(inBody('[data-testid="service-mode"]')!.textContent).toContain('Deducted')
    await debounce()
    expect(efmv.previewScenario).toHaveBeenLastCalledWith(
      expect.objectContaining({
        items: [
          expect.objectContaining({
            // Not named: the placeholder's name
            service: { name: 'Service', mode: 'deduct', percent: '8' },
          }),
        ],
      }),
    )
    // Removing the service — its row selected — (its value goes back to the asset: nothing sent)
    await click('service-row')
    expect(inBody('[data-testid="service-row"]')!.className).toContain('row-selected')
    expect(inBody('[data-testid="asset-row"]')!.className).not.toContain('row-selected')
    await click('remove-selected')
    expect(inBody('[data-testid="service-row"]')).toBeNull()
    expect(document.querySelectorAll('[data-testid="asset-row"]')).toHaveLength(1)
    expect(count('sv')).toBe('SV 0')
    await click('save')
    expect(efmv.updateEfmvAnalysis).toHaveBeenCalledWith(3, {
      scenarios: [
        expect.objectContaining({
          items: [{ average_price: 7, quantity: 2, unit_value: '100000.00', efmv_value: null }],
        }),
      ],
    })
    wrapper.unmount()
  })

  it("a deducted service shows the asset's value without it (the value typed when editing)", async () => {
    const service = { name: 'Warranty', mode: 'deduct' as const, value: '8000.00' }
    efmv.getEfmvAnalysis.mockResolvedValue({
      ...ANALYSIS,
      scenarios: [
        {
          ...ANALYSIS.scenarios[0]!,
          items: [
            {
              ...EXCAVATOR,
              net_unit_value: '92000.00',
              service: {
                ...service,
                line_total: '16000.00',
                weight_percent: '8.00',
                too_high: false,
              },
            },
          ],
        },
      ],
    })
    const { wrapper } = await mountView()
    const field = () => inBody('[data-testid="unit-value"] input') as HTMLInputElement
    expect(field().value).toBe('92,000.00')
    expect(inBody('[data-testid="unit-value"]')!.className).toContain('net-shown')
    // Editing: the value typed
    field().dispatchEvent(new Event('focus'))
    await settle()
    expect(field().value).toBe('100,000.00')
    field().dispatchEvent(new Event('blur'))
    await settle()
    expect(field().value).toBe('92,000.00')
    // Without the service: the value typed again
    await click('service-row')
    await click('remove-selected')
    expect(field().value).toBe('100,000.00')
    wrapper.unmount()
  })

  it("a right click selects the row and opens the toolbar's options", async () => {
    // jsdom has no layout: the menu placed at the click asks what is under the pointer
    document.elementsFromPoint = () => []
    efmv.getEfmvAnalysis.mockResolvedValue({
      ...ANALYSIS,
      scenarios: [
        { ...ANALYSIS.scenarios[0]!, items: [EXCAVATOR, { ...EXCAVATOR, id: 2, quantity: 5 }] },
      ],
    })
    const { wrapper } = await mountView()
    const rows = () => document.querySelectorAll<HTMLElement>('[data-testid="asset-row"]')
    expect(rows()).toHaveLength(2)
    rows()[1]!.dispatchEvent(
      new MouseEvent('contextmenu', { bubbles: true, clientX: 300, clientY: 400 }),
    )
    await settle()
    expect(rows()[1]!.className).toContain('row-selected')
    const menu = inBody('[data-testid="row-menu-list"]')!
    expect(menu.textContent).toContain('Add Hardware')
    expect(menu.textContent).toContain('Attach Service')
    expect(menu.textContent).toContain('Remove')
    // Attach a service to that asset from the menu
    await click('menu-attach-service')
    expect(document.querySelectorAll('[data-testid="service-row"]')).toHaveLength(1)
    // Remove the first asset from its menu
    rows()[0]!.dispatchEvent(
      new MouseEvent('contextmenu', { bubbles: true, clientX: 300, clientY: 300 }),
    )
    await settle()
    await click('menu-remove')
    expect(rows()).toHaveLength(1)
    // No row selected now: the toolbar has nothing to act on
    expect(inBody('[data-testid="remove-selected"]')!.hasAttribute('disabled')).toBe(true)
    wrapper.unmount()
  })

  it('Smart Tools: the scope written from the assets is the placeholder; typed text is kept', async () => {
    efmv.getEfmvAnalysis.mockResolvedValue({
      ...ANALYSIS,
      scenarios: [{ ...ANALYSIS.scenarios[0]!, scope: '' }],
    })
    efmv.updateEfmvAnalysis.mockResolvedValue(ANALYSIS)
    const { wrapper } = await mountView()
    const scope = () => inBody('[data-testid="scenario-scope"] textarea') as HTMLTextAreaElement
    // Empty: the text from the assets, in gray (nothing written in the field)
    expect(scope().value).toBe('')
    expect(scope().placeholder).toBe('Caterpillar Excavators')
    // No hint under the field (removed)
    expect(inBody('[data-testid="scenario-scope"]')!.textContent).not.toContain('Empty:')
    // It follows the assets
    efmv.previewScenario.mockResolvedValue({
      items: [EXCAVATOR],
      totals: TOTALS,
      has_expired: false,
      scope_suggestion: 'Caterpillar Excavators and Komatsu Loaders',
    })
    await typeInto('quantity', '3')
    await debounce()
    expect(scope().placeholder).toBe('Caterpillar Excavators and Komatsu Loaders')
    // Typed: the analyst's; changes in the grid never touch it
    await typeInto('scenario-scope', 'Yellow line fleet')
    await typeInto('quantity', '4')
    await debounce()
    expect(scope().value).toBe('Yellow line fleet')
    // The wand puts the text from the assets in the field, to edit it
    await click('scope-write')
    expect(scope().value).toBe('Caterpillar Excavators and Komatsu Loaders')
    // Saved as typed (empty when not typed)
    await click('save')
    expect(efmv.updateEfmvAnalysis).toHaveBeenCalledWith(3, {
      scenarios: [expect.objectContaining({ scope: 'Caterpillar Excavators and Komatsu Loaders' })],
    })
    wrapper.unmount()
  })

  it('Smart Tools: no text from the assets when turned off', async () => {
    efmv.getEfmvAnalysis.mockResolvedValue({
      ...ANALYSIS,
      scenarios: [{ ...ANALYSIS.scenarios[0]!, scope: '' }],
    })
    localStorage.setItem('horizon.autoScope', 'false')
    const { wrapper } = await mountView()
    const scope = inBody('[data-testid="scenario-scope"] textarea') as HTMLTextAreaElement
    expect(scope.placeholder).not.toBe('Caterpillar Excavators')
    expect(inBody('[data-testid="scope-write"]')!.hasAttribute('disabled')).toBe(true)
    localStorage.removeItem('horizon.autoScope')
    wrapper.unmount()
  })

  it('an empty row is left out when saving', async () => {
    efmv.getEfmvAnalysis.mockResolvedValue(ANALYSIS)
    efmv.updateEfmvAnalysis.mockResolvedValue(ANALYSIS)
    const { wrapper } = await mountView({ id: 3 })
    await addRow()
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

  it('adds software and a service of their own and attaches software to hardware', async () => {
    efmv.getEfmvAnalysis.mockResolvedValue(ANALYSIS)
    efmv.updateEfmvAnalysis.mockResolvedValue(ANALYSIS)
    const { wrapper } = await mountView({ id: 3 })
    await addRow('sv')
    await addRow('sw')
    const descriptions = document.querySelectorAll<HTMLInputElement>(
      '[data-testid="description"] input',
    )
    // Not described: the placeholder says what it is
    expect([...descriptions].map((d) => d.placeholder)).toEqual(['Service', 'Software'])
    // The new lines (found by their description cell)
    const lines = () =>
      [...document.querySelectorAll<HTMLElement>('[data-testid="description"]')].map((cell) =>
        cell.closest('tr')!,
      )
    for (const [index, text] of [
      [0, '2,000'],
      [1, '500'],
    ] as const) {
      const input = lines()[index]!.querySelector<HTMLInputElement>(
        '[data-testid="unit-value"] input',
      )!
      input.value = text
      input.dispatchEvent(new Event('input'))
      await settle()
    }
    // A service is not resold: its eFMV cannot be typed; software's can
    const efmvOf = (row: HTMLElement) =>
      row.querySelector<HTMLInputElement>('[data-testid="efmv-value"] input')!
    expect(efmvOf(lines()[0]!).disabled).toBe(true)
    expect(efmvOf(lines()[1]!).disabled).toBe(false)
    // Software attached to the excavator
    await click('asset-row')
    await attach('software')
    expect(document.querySelectorAll('[data-testid="software-row"]')).toHaveLength(1)
    expect((inBody('[data-testid="software-name"] input') as HTMLInputElement).placeholder).toBe(
      'Software',
    )
    await click('save')
    expect(efmv.updateEfmvAnalysis).toHaveBeenCalledWith(3, {
      scenarios: [
        expect.objectContaining({
          items: [
            expect.objectContaining({
              average_price: 7,
              software: expect.objectContaining({ name: 'Software', mode: 'add', value: '0.00' }),
            }),
            expect.objectContaining({ kind: 'sv', description: '', unit_value: '2000' }),
            expect.objectContaining({ kind: 'sw', description: '', unit_value: '500' }),
          ],
        }),
      ],
    })
    wrapper.unmount()
  })
})
