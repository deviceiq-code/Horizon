import { createPinia, setActivePinia } from 'pinia'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { setLanguage } from '@/i18n'
import * as assetClassesApi from '@/modules/catalogs/asset-classes/api'
import * as manufacturersApi from '@/modules/catalogs/manufacturers/api'
import { useNotificationsStore } from '@/stores/notifications'
import { click, inBody, mountWithPlugins, pickOption, settle, typeInto } from '@/test-utils'
import * as pricesApi from '../api'
import AveragePricesView from '../AveragePricesView.vue'

vi.mock('../api', () => ({
  listAveragePrices: vi.fn<typeof pricesApi.listAveragePrices>(),
  getAveragePrice: vi.fn<typeof pricesApi.getAveragePrice>(),
  getAveragePriceHistory: vi.fn<typeof pricesApi.getAveragePriceHistory>(),
  createAveragePrice: vi.fn<typeof pricesApi.createAveragePrice>(),
  deleteAveragePrice: vi.fn<typeof pricesApi.deleteAveragePrice>(),
  previewAveragePrice: vi.fn<typeof pricesApi.previewAveragePrice>(),
}))
vi.mock('@/modules/catalogs/asset-classes/api', () => ({
  listAssetClasses: vi.fn<typeof assetClassesApi.listAssetClasses>(),
  getAssetClass: vi.fn<typeof assetClassesApi.getAssetClass>(),
}))
vi.mock('@/modules/catalogs/manufacturers/api', () => ({
  listManufacturers: vi.fn<typeof manufacturersApi.listManufacturers>(),
}))

const prices = vi.mocked(pricesApi)
const assetClasses = vi.mocked(assetClassesApi)
const manufacturers = vi.mocked(manufacturersApi)

const page = <T>(results: T[]) => ({ count: results.length, next: null, previous: null, results })

const HOURS = {
  key: 'hours',
  label: 'Operating hours',
  kind: 'number' as const,
  unit: 'h',
  required: true,
}

const EXCAVATORS: assetClassesApi.AssetClass = {
  id: 5,
  name: 'Excavators',
  icon: 'mdi-excavator',
  sub_vertical: 11,
  sub_vertical_detail: {
    id: 11,
    name: 'Yellow line',
    is_general: false,
    label: 'Industry / Yellow line',
    vertical: { id: 1, name: 'Industry', is_enabled: true },
    allowed_terms: [12, 24],
    recommended_term: 24,
  },
  liquidity: '4.0',
  value_retention: '4.0',
  technology_renewal: '1.0',
  usage_breadth: '3.0',
  remarketing_average: '3.00',
  keywords: [],
  notes: '',
  spec_template: [HOURS],
  is_enabled: true,
  created_at: '',
  updated_at: '',
}

const ROW: pricesApi.AveragePriceDetail = {
  id: 100,
  vertical: { id: 1, name: 'Industry' },
  sub_vertical: { id: 11, label: 'Industry / Yellow line' },
  asset_class: { id: 5, name: 'Excavators', icon: 'mdi-excavator' },
  manufacturer: { id: 7, name: 'Caterpillar' },
  model: '320 GC',
  description: 'Hydraulic excavator, 20 t class.',
  specs: [{ ...HOURS, value: '2500' }],
  currency: 'BRL',
  original_value: '100000.00',
  points: [
    { term_months: 12, mode: 'percent', amount: '70.0000', value: '70000.00', percent: '70.00' },
    { term_months: 24, mode: 'value', amount: '55000.0000', value: '55000.00', percent: '55.00' },
  ],
  increasing_terms: [],
  is_current: true,
  supersedes: 90,
  created_at: '2026-11-19T15:00:00Z',
  created_by_name: 'Ana Souza',
  deleted_at: null,
  curve: Array.from({ length: 25 }, (_, month) => ({
    month,
    value: '1.00',
    percent: '1.00',
    is_anchor: month % 12 === 0,
  })),
}
const OLD_VERSION: pricesApi.AveragePrice = {
  ...ROW,
  id: 90,
  original_value: '95000.00',
  is_current: false,
  supersedes: null,
}

const mountView = () => mountWithPlugins(AveragePricesView)

async function waitPreview() {
  await new Promise((r) => setTimeout(r, 450)) // preview is debounced (400 ms)
  await settle()
}

async function fillNew(wrapper: ReturnType<typeof mountView>) {
  await wrapper.find('[data-testid="new"]').trigger('click')
  await settle()
  await pickOption('asset-class', 'Excavators — Industry / Yellow line')
  await pickOption('manufacturer', 'Caterpillar')
  await typeInto('model', ' 320 GC ')
  await typeInto('description', 'Hydraulic excavator.')
  await typeInto('spec-hours', '2,500')
  await typeInto('original-value', '100,000.00')
  const amounts = document.body.querySelectorAll<HTMLInputElement>(
    '[data-testid="term-amount"] input',
  )
  amounts[0]!.value = '70'
  amounts[0]!.dispatchEvent(new Event('input'))
  await settle()
  // 24 months as a fixed value
  inBody('[data-testid="term-24"] [data-testid="mode-value"]')!.click()
  await settle()
  amounts[1]!.value = '55,000'
  amounts[1]!.dispatchEvent(new Event('input'))
  await settle()
}

describe('AveragePricesView', () => {
  beforeEach(() => {
    setLanguage('en')
    setActivePinia(createPinia())
    prices.listAveragePrices.mockResolvedValue(page([ROW]))
    prices.getAveragePrice.mockResolvedValue(ROW)
    prices.getAveragePriceHistory.mockResolvedValue([ROW, OLD_VERSION])
    prices.previewAveragePrice.mockResolvedValue({
      points: [
        { term_months: 12, value: '70000.00', percent: '70.00' },
        { term_months: 24, value: '55000.00', percent: '55.00' },
      ],
      increasing_terms: [],
      curve: [],
    })
    assetClasses.listAssetClasses.mockResolvedValue(page([EXCAVATORS]))
    assetClasses.getAssetClass.mockResolvedValue(EXCAVATORS)
    manufacturers.listManufacturers.mockResolvedValue(
      page([
        {
          id: 7,
          name: 'Caterpillar',
          reputation: '5.0',
          product_quality: '5.0',
          after_sales: '4.0',
          remarketing_average: '4.67',
          is_enabled: true,
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

  // --- Grid ----------------------------------------------------------------------------------

  it('lists rows with asset, model, original value and the % at each term', async () => {
    const wrapper = mountView()
    await settle()

    expect(prices.listAveragePrices).toHaveBeenCalledWith(
      expect.objectContaining({ ordering: '-created_at' }),
    )
    const text = wrapper.find('tbody tr').text()
    expect(text).toContain('Excavators')
    expect(text).toContain('Industry / Yellow line')
    expect(text).toContain('320 GC')
    expect(text).toContain('Caterpillar')
    expect(text).toMatch(/R\$\s?100,000\.00/)
    expect(text).toContain('12m · 70.00%')
    expect(text).toContain('24m · 55.00%')
    expect(text).toContain('Ana Souza')
    wrapper.unmount()
  })

  // --- Create --------------------------------------------------------------------------------

  it('creates a row: terms and fields come from the asset class sub-vertical', async () => {
    prices.createAveragePrice.mockResolvedValue({ ...ROW, id: 101 })
    const wrapper = mountView()
    await settle()

    await fillNew(wrapper)
    // Terms of the sub-vertical (12 and 24) and its template field are shown
    expect(inBody('[data-testid="term-12"]')).not.toBeNull()
    expect(inBody('[data-testid="term-36"]')).toBeNull()
    await waitPreview()
    expect(prices.previewAveragePrice).toHaveBeenLastCalledWith({
      original_value: '100000.00',
      points: [
        { term_months: 12, mode: 'percent', amount: '70' },
        { term_months: 24, mode: 'value', amount: '55000' },
      ],
    })
    // Resolved by the API, not computed here
    expect(inBody('[data-testid="term-12"] [data-testid="term-result"]')!.textContent).toMatch(
      /R\$\s?70,000\.00/,
    )
    await click('save')

    expect(prices.createAveragePrice).toHaveBeenCalledWith({
      asset_class: 5,
      manufacturer: 7,
      model: '320 GC',
      description: 'Hydraulic excavator.',
      specs: { hours: '2500' },
      currency: 'BRL',
      original_value: '100000.00',
      points: [
        { term_months: 12, mode: 'percent', amount: '70' },
        { term_months: 24, mode: 'value', amount: '55000' },
      ],
      supersedes: null,
    })
    expect(useNotificationsStore().text).toBe('Average price created.')
    wrapper.unmount()
  })

  it('warns (but allows saving) when a longer term is worth more', async () => {
    prices.previewAveragePrice.mockResolvedValue({
      points: [
        { term_months: 12, value: '70000.00', percent: '70.00' },
        { term_months: 24, value: '75000.00', percent: '75.00' },
      ],
      increasing_terms: [24],
      curve: [],
    })
    prices.createAveragePrice.mockResolvedValue({ ...ROW, id: 101 })
    const wrapper = mountView()
    await settle()

    await fillNew(wrapper)
    await waitPreview()
    expect(inBody('[data-testid="increasing-warning"]')!.textContent).toContain(
      'the value at 24 months is higher',
    )
    await click('save')
    expect(prices.createAveragePrice).toHaveBeenCalled()
    wrapper.unmount()
  })

  it('requires the template fields marked as required', async () => {
    const wrapper = mountView()
    await settle()

    await fillNew(wrapper)
    await typeInto('spec-hours', '')
    await click('save')

    expect(prices.createAveragePrice).not.toHaveBeenCalled()
    expect(inBody('[data-testid="spec-hours"]')!.closest('.v-input')!.textContent).toContain(
      'This field is required.',
    )
    wrapper.unmount()
  })

  // --- New version ---------------------------------------------------------------------------

  it('creates a new version prefilled from the row, superseding it', async () => {
    prices.createAveragePrice.mockResolvedValue({ ...ROW, id: 101, supersedes: 100 })
    const wrapper = mountView()
    await settle()

    await wrapper.find('[data-testid="edit"]').trigger('click')
    await settle()
    expect(assetClasses.getAssetClass).toHaveBeenCalledWith(5)
    const value = (id: string) => (inBody(`[data-testid="${id}"] input`) as HTMLInputElement).value
    expect(value('model')).toBe('320 GC')
    expect(value('original-value')).toBe('100,000.00')
    expect(value('spec-hours')).toBe('2,500')
    await typeInto('original-value', '110,000')
    await click('save')

    expect(prices.createAveragePrice).toHaveBeenCalledWith(
      expect.objectContaining({
        original_value: '110000',
        supersedes: 100,
        points: [
          { term_months: 12, mode: 'percent', amount: '70' },
          { term_months: 24, mode: 'value', amount: '55000.00' },
        ],
      }),
    )
    expect(useNotificationsStore().text).toBe(
      'New version created; the previous one is in the history.',
    )
    wrapper.unmount()
  })

  // --- Detail and history --------------------------------------------------------------------

  it('shows the details, the monthly curve and the history', async () => {
    const wrapper = mountView()
    await settle()

    await wrapper.find('[data-testid="view"]').trigger('click')
    await settle()
    expect(prices.getAveragePrice).toHaveBeenCalledWith(100)
    expect(inBody('[data-testid="detail-specs"]')!.textContent).toContain('2500')
    expect(inBody('[data-testid="detail-terms"]')!.textContent).toContain('% of original')

    await click('tab-curve')
    expect(document.body.querySelectorAll('[data-testid="curve-row"]')).toHaveLength(25)

    await click('tab-history')
    const items = document.body.querySelectorAll<HTMLElement>('[data-testid="history-item"]')
    expect(items).toHaveLength(2)
    expect(items[0]!.textContent).toContain('Version 2')
    expect(items[1]!.textContent).toContain('Version 1')

    // Open the previous version
    prices.getAveragePrice.mockResolvedValue({ ...ROW, ...OLD_VERSION, curve: ROW.curve })
    items[1]!.click()
    await settle()
    expect(prices.getAveragePrice).toHaveBeenLastCalledWith(90)
    expect(inBody('[data-testid="detail-original"]')!.textContent).toMatch(/95,000\.00/)
    expect(document.body.textContent).toContain('Previous version')
    expect(inBody('[data-testid="detail-new-version"]')).toBeNull()
    wrapper.unmount()
  })

  // --- Delete --------------------------------------------------------------------------------

  it('deletes (hides) a row, which stays in the history', async () => {
    prices.deleteAveragePrice.mockResolvedValue(undefined)
    const wrapper = mountView()
    await settle()

    await wrapper.find('[data-testid="delete"]').trigger('click')
    await settle()
    expect(document.body.textContent).toContain('stays in the history')
    await click('confirm-button')

    expect(prices.deleteAveragePrice).toHaveBeenCalledWith(100)
    expect(useNotificationsStore().text).toBe('Average price deleted (kept in the history).')
    wrapper.unmount()
  })
})
