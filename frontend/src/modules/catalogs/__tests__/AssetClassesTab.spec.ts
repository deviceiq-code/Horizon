import { createPinia, setActivePinia } from 'pinia'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { ApiError } from '@/api'
import { setLanguage } from '@/i18n'
import { useNotificationsStore } from '@/stores/notifications'
import { click, inBody, mountWithPlugins, pickOption, settle, typeInto } from '@/test-utils'
import * as assetClassesApi from '../asset-classes/api'
import AssetClassesTab from '../asset-classes/AssetClassesTab.vue'
import * as verticalsApi from '../verticals/api'

vi.mock('../asset-classes/api', async (importOriginal) => ({
  ...(await importOriginal<typeof import('../asset-classes/api')>()),
  listAssetClasses: vi.fn<typeof assetClassesApi.listAssetClasses>(),
  createAssetClass: vi.fn<typeof assetClassesApi.createAssetClass>(),
  updateAssetClass: vi.fn<typeof assetClassesApi.updateAssetClass>(),
  deleteAssetClass: vi.fn<typeof assetClassesApi.deleteAssetClass>(),
}))
vi.mock('../verticals/api', () => ({
  listSubVerticals: vi.fn<typeof verticalsApi.listSubVerticals>(),
}))

const api = vi.mocked(assetClassesApi)
const verticals = vi.mocked(verticalsApi)

const INDUSTRY = { id: 1, name: 'Industry', is_enabled: true }
const MINING = { id: 3, name: 'Mining', is_enabled: false }
const sub = (id: number, name: string, vertical: typeof INDUSTRY, is_general = false) => ({
  id,
  name,
  is_general,
  label: `${vertical.name} / ${name}`,
  vertical,
})
const INDUSTRY_GENERAL = sub(10, 'General', INDUSTRY, true)
const YELLOW_LINE = sub(11, 'Yellow line', INDUSTRY)
const MINING_GENERAL = sub(30, 'General', MINING, true)

const EXCAVATORS: assetClassesApi.AssetClass = {
  id: 100,
  name: 'Excavators',
  icon: 'mdi-excavator',
  sub_vertical: YELLOW_LINE.id,
  sub_vertical_detail: YELLOW_LINE,
  liquidity: '4.5',
  value_retention: '4.0',
  technology_renewal: '1.0',
  usage_breadth: '3.5',
  remarketing_average: '3.25',
  keywords: ['escavadeira', 'hidráulica'],
  notes: 'Crawler and wheeled.',
  is_enabled: true,
  created_at: '',
  updated_at: '',
}
// All ratings at 0 stars; its vertical was disabled since
const DRILLS: assetClassesApi.AssetClass = {
  ...EXCAVATORS,
  id: 101,
  name: 'Drills',
  icon: 'mdi-cube-outline',
  sub_vertical: MINING_GENERAL.id,
  sub_vertical_detail: MINING_GENERAL,
  liquidity: '0.0',
  value_retention: '0.0',
  technology_renewal: '0.0',
  usage_breadth: '0.0',
  remarketing_average: '0.00',
  keywords: [],
  notes: '',
  is_enabled: false,
}

const mountTab = () => mountWithPlugins(AssetClassesTab)

async function openNew(wrapper: ReturnType<typeof mountTab>) {
  await wrapper.find('[data-testid="new"]').trigger('click')
  await settle()
}

async function openEdit(wrapper: ReturnType<typeof mountTab>, row: number) {
  await wrapper.findAll('[data-testid="edit"]')[row]!.trigger('click')
  await settle()
}

/** Set a rating by clicking its star label (0–5 in half steps). */
async function rate(field: string, stars: number) {
  const rating = inBody(`[data-testid="rating-${field}"] [data-testid="stars"]`)!
  // With half-increments v-rating renders one label per value, in order: 0, 0.5, 1 … 5
  const labels = rating.querySelectorAll<HTMLElement>('label')
  labels[stars * 2]!.click()
  await settle()
}

async function rateAll() {
  await rate('liquidity', 3.5)
  await rate('value_retention', 4)
  await rate('technology_renewal', 1)
  await rate('usage_breadth', 2.5)
}

describe('AssetClassesTab', () => {
  beforeEach(() => {
    setLanguage('en')
    setActivePinia(createPinia())
    api.listAssetClasses.mockResolvedValue({
      count: 2,
      next: null,
      previous: null,
      results: [DRILLS, EXCAVATORS],
    })
    verticals.listSubVerticals.mockResolvedValue({
      count: 2,
      next: null,
      previous: null,
      results: [INDUSTRY_GENERAL, YELLOW_LINE],
    })
  })

  afterEach(() => {
    vi.clearAllMocks()
    document.body.innerHTML = ''
  })

  // --- Grid ----------------------------------------------------------------------------------

  it('lists asset classes with icon, keywords, sub-vertical, remarketing average and status', async () => {
    const wrapper = mountTab()
    await settle()

    const rows = wrapper.findAll('tbody tr')
    const [drills, excavators] = rows.map((r) => r.text())
    expect(excavators).toContain('Excavators')
    expect(excavators).toContain('escavadeira, hidráulica')
    expect(excavators).toContain('Industry / Yellow line')
    expect(excavators).toContain('3.3/ 5') // average 3.25, shown with one decimal
    expect(rows[1]!.find('.mdi-excavator').exists()).toBe(true)
    expect(drills).toContain('0.0/ 5')
    expect(drills).toContain('Mining / General')
    expect(drills).toContain('(Disabled)')
    expect(drills).toContain('Disabled')
    wrapper.unmount()
  })

  it('sorts by the remarketing average on the server', async () => {
    const wrapper = mountTab()
    await settle()
    api.listAssetClasses.mockClear()

    const header = wrapper.findAll('th').find((th) => th.text().includes('Remarketing'))!
    await header.trigger('click')
    await settle()

    expect(api.listAssetClasses).toHaveBeenLastCalledWith(
      expect.objectContaining({ ordering: 'remarketing_score' }),
    )
    wrapper.unmount()
  })

  it('sorts the sub-vertical column by vertical name', async () => {
    const wrapper = mountTab()
    await settle()
    api.listAssetClasses.mockClear()

    const header = wrapper.findAll('th').find((th) => th.text().includes('sub-vertical'))!
    await header.trigger('click')
    await settle()

    expect(api.listAssetClasses).toHaveBeenLastCalledWith(
      expect.objectContaining({ ordering: 'sub_vertical__vertical__name' }),
    )
    wrapper.unmount()
  })

  // --- Create --------------------------------------------------------------------------------

  it('creates an asset class with icon, sub-vertical, ratings, keywords and notes', async () => {
    api.createAssetClass.mockResolvedValue({ ...EXCAVATORS, id: 102 })
    const wrapper = mountTab()
    await settle()

    await openNew(wrapper)
    expect(inBody('[data-testid="icon-current"]')!.className).toContain('mdi-cube-outline')
    await click('icon-choose')
    inBody('[data-testid="icon-option"][data-icon="mdi-crane"]')!.click()
    await settle()
    await typeInto('name', ' Mobile cranes ')
    await pickOption('sub-vertical', 'Industry / Yellow line')
    await rateAll()
    await typeInto('keyword-input', 'Guindaste, Içamento')
    inBody('[data-testid="keyword-input"] input')!.dispatchEvent(
      new KeyboardEvent('keydown', { key: 'Enter', bubbles: true }),
    )
    await settle()
    await typeInto('notes', 'Truck-mounted.')
    await click('save')

    expect(verticals.listSubVerticals).toHaveBeenCalledWith(
      expect.objectContaining({ filters: { is_enabled: true } }),
    )
    expect(api.createAssetClass).toHaveBeenCalledWith({
      name: 'Mobile cranes',
      icon: 'mdi-crane',
      sub_vertical: YELLOW_LINE.id,
      liquidity: '3.5',
      value_retention: '4.0',
      technology_renewal: '1.0',
      usage_breadth: '2.5',
      keywords: ['guindaste', 'içamento'],
      notes: 'Truck-mounted.',
      is_enabled: true,
    })
    expect(useNotificationsStore().text).toBe('Asset class created.')
    wrapper.unmount()
  })

  it('requires the sub-vertical; ratings not filled in are 0 stars', async () => {
    api.createAssetClass.mockResolvedValue({ ...DRILLS, id: 103 })
    const wrapper = mountTab()
    await settle()

    await openNew(wrapper)
    await typeInto('name', 'Cranes')
    await rate('liquidity', 3)
    await click('save')

    expect(api.createAssetClass).not.toHaveBeenCalled()
    expect(inBody('[data-testid="sub-vertical"]')!.closest('.v-input')!.textContent).toContain(
      'This field is required.',
    )
    expect(document.body.textContent).not.toContain('Not rated')

    await pickOption('sub-vertical', 'Industry / General')
    await click('save')
    expect(api.createAssetClass).toHaveBeenCalledWith(
      expect.objectContaining({
        liquidity: '3.0',
        value_retention: '0.0',
        technology_renewal: '0.0',
        usage_breadth: '0.0',
      }),
    )
    wrapper.unmount()
  })

  it('shows the average live while rating', async () => {
    const wrapper = mountTab()
    await settle()

    await openNew(wrapper)
    const preview = () => inBody('[data-testid="average-preview"]')!.textContent
    expect(preview()).toContain('0.0')
    await rateAll() // 3.5 + 4 + 1 + 2.5 = 11 / 4 = 2.75
    expect(preview()).toContain('2.8')
    wrapper.unmount()
  })

  // --- Edit ----------------------------------------------------------------------------------

  it('edits an asset class keeping its values', async () => {
    api.updateAssetClass.mockResolvedValue(EXCAVATORS)
    const wrapper = mountTab()
    await settle()

    await openEdit(wrapper, 1)
    expect(inBody('[data-testid="sub-vertical"]')!.textContent).toContain('Industry / Yellow line')
    expect(
      inBody('[data-testid="rating-liquidity"] [data-testid="stars-value"]')!.textContent,
    ).toContain('4.5 / 5')
    const chips = [...document.body.querySelectorAll('[data-testid="keyword-chip"]')].map((c) =>
      c.textContent?.trim(),
    )
    expect(chips).toEqual(['escavadeira', 'hidráulica'])
    // Remove a keyword and change one rating
    inBody('[data-testid="keyword-chip"] .v-chip__close')!.click()
    await settle()
    await rate('technology_renewal', 2)
    await click('save')

    expect(api.updateAssetClass).toHaveBeenCalledWith(100, {
      name: 'Excavators',
      icon: 'mdi-excavator',
      sub_vertical: YELLOW_LINE.id,
      liquidity: '4.5',
      value_retention: '4.0',
      technology_renewal: '2.0',
      usage_breadth: '3.5',
      keywords: ['hidráulica'],
      notes: 'Crawler and wheeled.',
      is_enabled: true,
    })
    wrapper.unmount()
  })

  it('edits a class whose vertical was disabled since', async () => {
    api.updateAssetClass.mockResolvedValue(DRILLS)
    const wrapper = mountTab()
    await settle()

    await openEdit(wrapper, 0) // Drills: zero stars, vertical disabled since
    expect(inBody('[data-testid="sub-vertical"]')!.textContent).toContain(
      'Mining / General (Disabled)',
    )
    expect(inBody('[data-testid="rating-liquidity"]')!.textContent).toContain('0.0 / 5')
    await rateAll()
    await click('save')
    expect(api.updateAssetClass).toHaveBeenCalledWith(
      101,
      expect.objectContaining({ sub_vertical: MINING_GENERAL.id, liquidity: '3.5' }),
    )
    wrapper.unmount()
  })

  // --- Server errors and delete --------------------------------------------------------------

  it('shows the server validation error on the name field', async () => {
    api.createAssetClass.mockRejectedValue(
      new ApiError(400, 'Bad Request', {
        name: ['This sub-vertical already has an asset class with this name.'],
      }),
    )
    const wrapper = mountTab()
    await settle()

    await openNew(wrapper)
    await typeInto('name', 'excavators')
    await pickOption('sub-vertical', 'Industry / Yellow line')
    await rateAll()
    await click('save')

    expect(document.body.textContent).toContain(
      'This sub-vertical already has an asset class with this name.',
    )
    wrapper.unmount()
  })

  it('deletes after confirmation', async () => {
    api.deleteAssetClass.mockResolvedValue(undefined)
    const wrapper = mountTab()
    await settle()

    await wrapper.findAll('[data-testid="delete"]')[1]!.trigger('click')
    await settle()
    expect(document.body.textContent).toContain('Delete "Excavators"?')
    await click('confirm-button')

    expect(api.deleteAssetClass).toHaveBeenCalledWith(100)
    expect(useNotificationsStore().text).toBe('Asset class deleted.')
    wrapper.unmount()
  })
})
