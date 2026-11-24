import { createPinia, setActivePinia } from 'pinia'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { setLanguage } from '@/i18n'
import * as assetClassesApi from '@/modules/catalogs/asset-classes/api'
import * as manufacturersApi from '@/modules/catalogs/manufacturers/api'
import { useNotificationsStore } from '@/stores/notifications'
import { usePreferencesStore } from '@/stores/preferences'
import { click, inBody, mountWithPlugins, pickOption, settle, typeInto } from '@/test-utils'
import * as pricesApi from '../api'
import AveragePricesView from '../AveragePricesView.vue'

vi.mock('../api', async (importOriginal) => ({
  ...(await importOriginal<typeof import('../api')>()),
  listPriceDocuments: vi.fn<typeof pricesApi.listPriceDocuments>(),
  uploadPriceDocument: vi.fn<typeof pricesApi.uploadPriceDocument>(),
  uploadPricePhoto: vi.fn<typeof pricesApi.uploadPricePhoto>(),
  listAveragePrices: vi.fn<typeof pricesApi.listAveragePrices>(),
  getAveragePrice: vi.fn<typeof pricesApi.getAveragePrice>(),
  getAveragePriceHistory: vi.fn<typeof pricesApi.getAveragePriceHistory>(),
  createAveragePrice: vi.fn<typeof pricesApi.createAveragePrice>(),
  deleteAveragePrice: vi.fn<typeof pricesApi.deleteAveragePrice>(),
  deleteAveragePriceVersion: vi.fn<typeof pricesApi.deleteAveragePriceVersion>(),
  previewAveragePrice: vi.fn<typeof pricesApi.previewAveragePrice>(),
  getSpecSuggestions: vi.fn<typeof pricesApi.getSpecSuggestions>(),
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
  options: [],
}

const TRACKS = {
  key: 'tracks',
  label: 'Undercarriage',
  kind: 'text' as const,
  unit: '',
  required: false,
  options: [],
}

const EXCAVATORS: assetClassesApi.AssetClass = {
  id: 5,
  name: 'Excavators',
  plural_name: 'Excavators',
  translations: {},
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
  spec_template: [HOURS, TRACKS],
  required_photo_kinds: [],
  is_enabled: true,
  created_at: '',
  updated_at: '',
}

const ROW: pricesApi.AveragePriceDetail = {
  id: 100,
  keywords: [],
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
  documents_count: 0,
  photo_id: null,
  photo_source_url: '',
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

/** Confirm in the dialog that is open (other confirmation dialogs may stay in the DOM). */
async function confirmOpenDialog() {
  inBody('.v-overlay--active [data-testid="confirm-button"]')!.click()
  await settle()
}

async function waitPreview() {
  await new Promise((r) => setTimeout(r, 450)) // preview is debounced (400 ms)
  await settle()
}

async function fillNew(
  wrapper: ReturnType<typeof mountView>,
  description = 'Hydraulic excavator.',
) {
  await wrapper.find('[data-testid="new"]').trigger('click')
  await settle()
  await pickOption('asset-class', 'Excavators — Industry / Yellow line')
  await pickOption('manufacturer', 'Caterpillar')
  await typeInto('model', ' 320 GC ')
  if (description) await typeInto('description', description)
  await typeInto('spec-hours', '2,500')
  await typeInto('original-value', '100,000.00')
  const amounts = document.body.querySelectorAll<HTMLInputElement>(
    '[data-testid="term-amount"] input',
  )
  // 12 months as a % of the original value, 24 months as a value: the same field
  amounts[0]!.value = '70%'
  amounts[0]!.dispatchEvent(new Event('input'))
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
    prices.getAveragePriceHistory.mockResolvedValue({
      versions: [ROW, OLD_VERSION],
      average: {
        count: 2,
        original_value: '97500.00',
        points: [
          { term_months: 12, value: '68000.00', percent: '69.74', count: 2 },
          { term_months: 24, value: '55000.00', percent: '57.89', count: 1 },
        ],
      },
    })
    prices.getSpecSuggestions.mockResolvedValue(['Steel', 'Steel with rubber pads'])
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
          keywords: [],
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

  // --- Column filters -------------------------------------------------------------------------

  it('filters by the columns: asset class, model, value range and dates', async () => {
    const wrapper = mountView()
    await settle()
    // Off until turned on
    expect(inBody('[data-testid="filter-row"]')).toBeNull()
    await click('toggle-filters')
    expect(inBody('[data-testid="filter-row"]')).not.toBeNull()
    expect(inBody('[data-testid="clear-filters"]')).toBeNull()
    const lastFilters = () => prices.listAveragePrices.mock.lastCall![0].filters
    const pause = () => new Promise((r) => setTimeout(r, 400))

    await typeInto('filter-model', '320')
    await typeInto('filter-value-min', '90,000.50')
    await pause()
    await settle()
    expect(lastFilters()).toEqual({ model: '320', original_value_min: '90000.50' })
    expect(prices.listAveragePrices.mock.lastCall![0].page).toBe(1)

    await pickOption('filter-asset-class', 'Excavators — Industry / Yellow line')
    await typeInto('filter-created-from', '2026-11-01')
    expect(lastFilters()).toEqual({
      model: '320',
      original_value_min: '90000.50',
      asset_class: 5,
      created_from: '2026-11-01',
    })

    // A value that cannot be read is flagged and not sent
    await typeInto('filter-value-max', 'abc')
    await pause()
    await settle()
    expect(inBody('[data-testid="filter-value-max"]')!.className).toContain('v-input--error')
    expect(lastFilters()).not.toHaveProperty('original_value_max')

    await click('clear-filters')
    expect(lastFilters()).toEqual({})
    expect((inBody('[data-testid="filter-model"] input') as HTMLInputElement).value).toBe('')
    expect(inBody('[data-testid="clear-filters"]')).toBeNull()

    // Turning the filters off clears them; the choice is remembered with the account
    await typeInto('filter-model', '320')
    await pause()
    await settle()
    expect(lastFilters()).toEqual({ model: '320' })
    await click('toggle-filters')
    expect(inBody('[data-testid="filter-row"]')).toBeNull()
    expect(lastFilters()).toEqual({})
    expect(usePreferencesStore().uiState.filters).toEqual({ 'average-prices': false })
    wrapper.unmount()
  })

  it('remembers that the filters were on', async () => {
    // As saved with the account (on another computer, too)
    usePreferencesStore().apply({ ui_state: { filters: { 'average-prices': true } } })
    const wrapper = mountView()
    await settle()
    expect(inBody('[data-testid="filter-row"]')).not.toBeNull()
    wrapper.unmount()
  })

  // --- Create --------------------------------------------------------------------------------

  it('creates a row: terms and fields come from the asset class sub-vertical', async () => {
    prices.createAveragePrice.mockResolvedValue({ ...ROW, id: 101 })
    const wrapper = mountView()
    await settle()

    await fillNew(wrapper)
    // Text specification: values already used are offered while typing
    await typeInto('spec-tracks', 'ste')
    await new Promise((r) => setTimeout(r, 300)) // debounced
    await settle()
    expect(prices.getSpecSuggestions).toHaveBeenLastCalledWith(5, 'tracks', 'ste')
    await pickOption('spec-tracks', 'Steel')
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
    // Resolved by the API, not computed here: its share of the original value below it
    expect(inBody('[data-testid="term-12"] [data-testid="term-percent"]')!.textContent).toContain(
      '% Value (70.00%)',
    )
    // Leaving the field, the % becomes its value (from the API)
    const twelve = inBody('[data-testid="term-12"] input') as HTMLInputElement
    twelve.dispatchEvent(new Event('blur'))
    await settle()
    expect(twelve.value).toBe('70,000.00')
    await waitPreview()
    await click('save')

    expect(prices.createAveragePrice).toHaveBeenCalledWith({
      asset_class: 5,
      manufacturer: 7,
      model: '320 GC',
      description: 'Hydraulic excavator.',
      keywords: [],
      specs: { hours: '2500', tracks: 'Steel' },
      currency: 'BRL',
      original_value: '100000.00',
      points: [
        { term_months: 12, mode: 'value', amount: '70000.00' },
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

  it('two tabs, the asset and its eFMV; saving opens the one with what is missing', async () => {
    const wrapper = mountView()
    await settle()
    await wrapper.find('[data-testid="new"]').trigger('click')
    await settle()
    const active = () => inBody('.v-tab--selected')!.getAttribute('data-testid')
    expect(active()).toBe('tab-asset')
    await pickOption('asset-class', 'Excavators — Industry / Yellow line')
    await pickOption('manufacturer', 'Caterpillar')
    await typeInto('model', '320 GC')
    await typeInto('spec-hours', '2,500')
    // The asset is complete; its values are not
    await click('save')
    await settle()
    expect(prices.createAveragePrice).not.toHaveBeenCalled()
    expect(active()).toBe('tab-efmv')
    // And back: the asset's tab with what is missing there
    await typeInto('model', '')
    await click('save')
    await settle()
    expect(active()).toBe('tab-asset')
    wrapper.unmount()
  })

  it('saves without a detailed description (optional)', async () => {
    prices.createAveragePrice.mockResolvedValue({ ...ROW, id: 101, description: '' })
    const wrapper = mountView()
    await settle()

    await fillNew(wrapper, '')
    await waitPreview()
    await click('save')
    expect(prices.createAveragePrice).toHaveBeenCalledWith(
      expect.objectContaining({ description: '' }),
    )
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

  it('only the photo or documents changed: applied to the row, no new version', async () => {
    prices.listPriceDocuments.mockResolvedValue([])
    prices.uploadPriceDocument.mockResolvedValue({} as pricesApi.PriceDocument)
    const wrapper = mountView()
    await settle()
    await wrapper.find('[data-testid="edit"]').trigger('click')
    await settle()
    await click('tab-media')
    const file = new File(['pdf'], 'Catalog.pdf', { type: 'application/pdf' })
    const input = inBody('[data-testid="documents-input"]') as HTMLInputElement
    Object.defineProperty(input, 'files', { value: [file], configurable: true })
    input.dispatchEvent(new Event('change'))
    await settle()
    await waitPreview()
    await click('save')
    await settle()

    expect(prices.createAveragePrice).not.toHaveBeenCalled()
    expect(prices.uploadPriceDocument).toHaveBeenCalledWith(100, file)
    expect(useNotificationsStore().text).toBe('Photo and documents saved.')
    wrapper.unmount()
  })

  it('nothing changed: nothing is saved', async () => {
    prices.listPriceDocuments.mockResolvedValue([])
    const wrapper = mountView()
    await settle()
    await wrapper.find('[data-testid="edit"]').trigger('click')
    await settle()
    await waitPreview()
    await click('save')
    await settle()
    expect(prices.createAveragePrice).not.toHaveBeenCalled()
    expect(useNotificationsStore().text).toBe('Nothing changed.')
    wrapper.unmount()
  })

  it('a new price gets its photo once created', async () => {
    prices.createAveragePrice.mockResolvedValue({ ...ROW, id: 101 })
    prices.uploadPricePhoto.mockResolvedValue({ photo_id: 5 })
    URL.createObjectURL = vi.fn<(object: Blob) => string>(() => 'blob:photo')
    const wrapper = mountView()
    await settle()
    await fillNew(wrapper)
    await click('tab-media')
    const photo = new File(['jpeg'], 'front.jpg', { type: 'image/jpeg' })
    const input = inBody('[data-testid="photo-input"]') as HTMLInputElement
    Object.defineProperty(input, 'files', { value: [photo], configurable: true })
    input.dispatchEvent(new Event('change'))
    await settle()
    await waitPreview()
    await click('save')
    await settle()
    expect(prices.createAveragePrice).toHaveBeenCalled()
    expect(prices.uploadPricePhoto).toHaveBeenCalledWith(101, photo)
    expect(useNotificationsStore().text).toBe('Average price created.')
    wrapper.unmount()
  })

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
    // The model is searched on the Internet with its manufacturer
    const open = vi.spyOn(window, 'open').mockReturnValue(null)
    ;(inBody('[data-testid="model"] [data-testid="web-search"]') as HTMLButtonElement).click()
    expect(open).toHaveBeenCalledWith(
      'https://www.google.com/search?q=Caterpillar%20320%20GC',
      '_blank',
      'noopener,noreferrer',
    )
    open.mockRestore()
    expect(value('spec-hours')).toBe('2,500')
    await typeInto('original-value', '110,000')
    await click('save')

    expect(prices.createAveragePrice).toHaveBeenCalledWith(
      expect.objectContaining({
        original_value: '110000',
        supersedes: 100,
        // Shown and sent as values (as the eFMV cells)
        points: [
          { term_months: 12, mode: 'value', amount: '70000.00' },
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
    expect(inBody('[data-testid="detail-terms"]')!.textContent).toContain('% of Original')

    await click('tab-curve')
    expect(document.body.querySelectorAll('[data-testid="curve-row"]')).toHaveLength(25)

    await click('tab-history')
    const items = document.body.querySelectorAll<HTMLElement>('[data-testid="history-item"]')
    expect(items).toHaveLength(2)
    expect(items[0]!.textContent).toContain('11/19/2026')
    expect(items[0]!.textContent).not.toContain('Version')

    // Open the previous version
    prices.getAveragePrice.mockResolvedValue({ ...ROW, ...OLD_VERSION, curve: ROW.curve })
    items[1]!.click()
    await settle()
    expect(prices.getAveragePrice).toHaveBeenLastCalledWith(90)
    expect(inBody('[data-testid="detail-original"]')!.textContent).toMatch(/95,000\.00/)
    expect(document.body.textContent).toContain('Previous Version')
    expect(inBody('[data-testid="detail-new-version"]')).toBeNull()
    wrapper.unmount()
  })

  // --- Delete --------------------------------------------------------------------------------

  it('deletes a row with all its versions (kept as history)', async () => {
    prices.deleteAveragePrice.mockResolvedValue(undefined)
    const wrapper = mountView()
    await settle()

    await wrapper.find('[data-testid="delete"]').trigger('click')
    await settle()
    expect(document.body.textContent).toContain('and all its versions')
    await confirmOpenDialog()

    expect(prices.deleteAveragePrice).toHaveBeenCalledWith(100)
    expect(useNotificationsStore().text).toBe(
      'Average price deleted with all its versions (kept as history).',
    )
    wrapper.unmount()
  })

  // --- Previous versions in the grid ---------------------------------------------------------

  it('expands a row to show all its versions, their average, and delete one', async () => {
    const SINGLE = { ...ROW, id: 200, supersedes: null }
    prices.listAveragePrices.mockResolvedValue(page([ROW, SINGLE]))
    prices.deleteAveragePriceVersion.mockResolvedValue(undefined)
    const wrapper = mountView()
    await settle()

    // Only rows with previous versions can expand
    const toggles = wrapper.findAll('[data-testid="expand"]')
    expect(toggles).toHaveLength(1)
    await toggles[0]!.trigger('click')
    await settle()

    expect(prices.getAveragePriceHistory).toHaveBeenCalledWith(100)
    const panel = inBody('[data-testid="versions-panel"]')!
    expect(panel.textContent).toContain('All versions (2)')
    // Every version, the current one included
    const items = panel.querySelectorAll<HTMLElement>('[data-testid="history-item"]')
    expect(items).toHaveLength(2)
    expect(items[0]!.textContent).toContain('Current')
    expect(items[1]!.textContent).toMatch(/95,000\.00/)
    expect(items[1]!.textContent).toContain('12m · 70.00%')
    // And their average
    expect(panel.querySelector('[data-testid="history-average"]')!.textContent).toContain(
      'Average of the history (2 versions)',
    )

    prices.getAveragePriceHistory.mockResolvedValue({ versions: [ROW], average: null })
    prices.listAveragePrices.mockClear()
    items[1]!.querySelector<HTMLElement>('[data-testid="delete-version"]')!.click()
    await settle()
    expect(document.body.textContent).toContain('Delete the version of 11/19/2026')
    expect(document.body.textContent).toContain('cannot be undone')
    await confirmOpenDialog()

    expect(prices.deleteAveragePriceVersion).toHaveBeenCalledWith(90)
    expect(useNotificationsStore().text).toBe('Version deleted.')
    // Erased: gone from the list (not marked as deleted); no average with one version left
    const after = inBody('[data-testid="versions-panel"]')!
    expect(after.querySelectorAll('[data-testid="history-item"]')).toHaveLength(1)
    expect(after.querySelector('[data-testid="history-average"]')).toBeNull()
    expect(prices.listAveragePrices).toHaveBeenCalled()
    wrapper.unmount()
  })

  it('shows the average of all versions in the history', async () => {
    const wrapper = mountView()
    await settle()
    await wrapper.find('[data-testid="view"]').trigger('click')
    await settle()
    await click('tab-history')

    const average = inBody('[data-testid="history-average"]')!
    expect(average.textContent).toContain('Average of the history (2 versions)')
    expect(average.textContent).toMatch(/R\$\s?97,500\.00/)
    const points = average.querySelectorAll<HTMLElement>('[data-testid="average-point"]')
    expect(points[0]!.textContent).toMatch(/12 months\s*R\$\s?68,000\.00\s*· 69.74%/)
    // Term only in some versions: marked, with the explanation on hover
    expect(points[1]!.getAttribute('title')).toBe('Only 1 of the 2 versions have this term')
    wrapper.unmount()
  })

  it('erasing the version shown in the detail shows the newest one left', async () => {
    prices.deleteAveragePriceVersion.mockResolvedValue(undefined)
    const wrapper = mountView()
    await settle()
    await wrapper.find('[data-testid="view"]').trigger('click')
    await settle()
    await click('tab-history')

    prices.getAveragePrice.mockResolvedValue({
      ...ROW,
      ...OLD_VERSION,
      is_current: true,
      curve: [],
    })
    prices.getAveragePriceHistory.mockResolvedValue({
      versions: [{ ...OLD_VERSION, is_current: true }],
      average: null,
    })
    prices.listAveragePrices.mockClear()
    inBody('[data-testid="detail-history"] [data-testid="delete-version"]')!.click()
    await settle()
    await confirmOpenDialog()

    expect(prices.deleteAveragePriceVersion).toHaveBeenCalledWith(100)
    expect(prices.getAveragePrice).toHaveBeenLastCalledWith(90)
    expect(prices.listAveragePrices).toHaveBeenCalled()
    expect(inBody('[data-testid="detail-original"]')!.textContent).toMatch(/95,000\.00/)
    expect(inBody('[data-testid="history-average"]')).toBeNull() // a single version left
    wrapper.unmount()
  })

  it('erasing the only version closes the detail', async () => {
    prices.deleteAveragePriceVersion.mockResolvedValue(undefined)
    prices.getAveragePriceHistory.mockResolvedValue({ versions: [ROW], average: null })
    const wrapper = mountView()
    await settle()
    await wrapper.find('[data-testid="view"]').trigger('click')
    await settle()
    await click('tab-history')

    inBody('[data-testid="detail-history"] [data-testid="delete-version"]')!.click()
    await settle()
    await confirmOpenDialog()

    expect(prices.deleteAveragePriceVersion).toHaveBeenCalledWith(100)
    expect(inBody('.v-overlay--active [data-testid="detail-original"]')).toBeNull()
    wrapper.unmount()
  })

  it('compares up to three prices as cards; the best eFMV at each term wins', async () => {
    const OTHER = {
      ...ROW,
      id: 101,
      model: '323 GC',
      points: [
        { ...ROW.points[0]!, value: '75000.00', percent: '75.00' },
        { ...ROW.points[1]!, value: '50000.00', percent: '50.00' },
      ],
    }
    const THIRD = { ...ROW, id: 102, model: '336 GC' }
    const FOURTH = { ...ROW, id: 103, model: '349 GC' }
    prices.listAveragePrices.mockResolvedValue(page([ROW, OTHER, THIRD, FOURTH]))
    prices.getAveragePrice.mockImplementation(async (id) =>
      [ROW, OTHER, THIRD, FOURTH].find((r) => r.id === id)!,
    )
    const wrapper = mountView()
    await settle()
    expect(wrapper.find('.v-data-table input[type="checkbox"]').exists()).toBe(false)
    await wrapper.find('[data-testid="compare-start"]').trigger('click')
    await settle()
    expect(wrapper.find('[data-testid="compare-open"]').attributes('disabled')).toBeDefined()
    const boxes = () => wrapper.findAll('.v-data-table tbody input[type="checkbox"]')
    await boxes()[0]!.trigger('click')
    await settle()
    await boxes()[1]!.trigger('click')
    await settle()
    expect(wrapper.find('[data-testid="compare-count"]').text()).toBe('2 of 3 selected')
    await wrapper.find('[data-testid="compare-open"]').trigger('click')
    await settle()
    const cards = document.body.querySelectorAll('[data-testid="compare-card"]')
    expect(cards).toHaveLength(2)
    const models = document.body.querySelectorAll('[data-testid="compare-model"]')
    expect(models[0]!.textContent).toContain('320 GC')
    // Aligned: each term is one line with a cell per card
    expect(document.body.querySelectorAll('[data-testid="compare-term"]')).toHaveLength(4)
    // 12 months: 75% beats 70%; 24 months: 55% beats 50% — one win each
    const wins = [...document.body.querySelectorAll('[data-testid="compare-wins"]')].map((w) =>
      w.textContent?.trim(),
    )
    expect(wins).toEqual(['1', '1'])
    const best = document.body.querySelectorAll('.best[data-card="1"]')
    expect(best).toHaveLength(1)
    expect(best[0]!.textContent).toContain('75.00%')
    wrapper.unmount()
  })
})
