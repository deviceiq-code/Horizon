import { createPinia, setActivePinia } from 'pinia'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { ApiError } from '@/api'
import { setLanguage } from '@/i18n'
import { useNotificationsStore } from '@/stores/notifications'
import { click, inBody, mountWithPlugins, settle, typeInto } from '@/test-utils'
import * as manufacturersApi from '../manufacturers/api'
import ManufacturersTab from '../manufacturers/ManufacturersTab.vue'

vi.mock('../manufacturers/api', async (importOriginal) => ({
  ...(await importOriginal<typeof import('../manufacturers/api')>()),
  listManufacturers: vi.fn<typeof manufacturersApi.listManufacturers>(),
  createManufacturer: vi.fn<typeof manufacturersApi.createManufacturer>(),
  updateManufacturer: vi.fn<typeof manufacturersApi.updateManufacturer>(),
  deleteManufacturer: vi.fn<typeof manufacturersApi.deleteManufacturer>(),
}))

const api = vi.mocked(manufacturersApi)

const DEERE: manufacturersApi.Manufacturer = {
  id: 1,
  name: 'John Deere',
  reputation: '5.0',
  product_quality: '4.5',
  after_sales: '4.0',
  remarketing_average: '4.50',
  is_enabled: true,
  created_at: '',
  updated_at: '',
}
const ACME: manufacturersApi.Manufacturer = {
  ...DEERE,
  id: 2,
  name: 'Acme',
  reputation: '0.0',
  product_quality: '0.0',
  after_sales: '0.0',
  remarketing_average: '0.00',
  is_enabled: false,
}

const mountTab = () => mountWithPlugins(ManufacturersTab)

/** Set a rating by clicking its star label (0–5 in half steps). */
async function rate(field: string, stars: number) {
  const rating = inBody(`[data-testid="rating-${field}"] [data-testid="stars"]`)!
  // With half-increments v-rating renders one label per value, in order: 0, 0.5, 1 … 5
  rating.querySelectorAll<HTMLElement>('label')[stars * 2]!.click()
  await settle()
}

const averagePreview = () => inBody('[data-testid="average-preview"]')!.textContent

describe('ManufacturersTab', () => {
  beforeEach(() => {
    setLanguage('en')
    setActivePinia(createPinia())
    api.listManufacturers.mockResolvedValue({
      count: 2,
      next: null,
      previous: null,
      results: [ACME, DEERE],
    })
  })

  afterEach(() => {
    vi.clearAllMocks()
    document.body.innerHTML = ''
  })

  it('lists manufacturers with the remarketing average and status', async () => {
    const wrapper = mountTab()
    await settle()

    const [acme, deere] = wrapper.findAll('tbody tr').map((r) => r.text())
    expect(deere).toContain('John Deere')
    expect(deere).toContain('4.5/ 5')
    expect(deere).toContain('Enabled')
    expect(acme).toContain('0.0/ 5')
    expect(acme).toContain('Disabled')
    wrapper.unmount()
  })

  it('formats the average for the UI language', async () => {
    setLanguage('pt-br')
    const wrapper = mountTab()
    await settle()

    expect(wrapper.findAll('tbody tr')[1]!.text()).toContain('4,5/ 5')
    wrapper.unmount()
  })

  it('sorts by the remarketing average on the server', async () => {
    const wrapper = mountTab()
    await settle()
    api.listManufacturers.mockClear()

    const header = wrapper.findAll('th').find((th) => th.text().includes('Remarketing'))!
    await header.trigger('click')
    await settle()

    expect(api.listManufacturers).toHaveBeenLastCalledWith(
      expect.objectContaining({ ordering: 'remarketing_score' }),
    )
    wrapper.unmount()
  })

  it('creates a manufacturer; ratings start at 0 and the average updates live', async () => {
    api.createManufacturer.mockResolvedValue({ ...DEERE, id: 3 })
    const wrapper = mountTab()
    await settle()

    await wrapper.find('[data-testid="new"]').trigger('click')
    await settle()
    expect(averagePreview()).toContain('0.0')
    await typeInto('name', ' New Holland ')
    await rate('reputation', 4.5)
    await rate('product_quality', 4)
    expect(averagePreview()).toContain('2.8') // (4.5 + 4 + 0) / 3 = 2.83
    await click('save')

    expect(api.createManufacturer).toHaveBeenCalledWith({
      name: 'New Holland',
      reputation: '4.5',
      product_quality: '4.0',
      after_sales: '0.0', // not filled in = 0 stars
      is_enabled: true,
    })
    expect(useNotificationsStore().text).toBe('Manufacturer created.')
    wrapper.unmount()
  })

  it('saves with every rating at zero stars', async () => {
    api.createManufacturer.mockResolvedValue({ ...ACME, id: 4 })
    const wrapper = mountTab()
    await settle()

    await wrapper.find('[data-testid="new"]').trigger('click')
    await settle()
    await typeInto('name', 'Unrated')
    await click('save')

    expect(api.createManufacturer).toHaveBeenCalledWith(
      expect.objectContaining({ reputation: '0.0', product_quality: '0.0', after_sales: '0.0' }),
    )
    wrapper.unmount()
  })

  it('clicking the selected star again sets the rating back to 0', async () => {
    const wrapper = mountTab()
    await settle()

    await wrapper.find('[data-testid="new"]').trigger('click')
    await settle()
    await rate('after_sales', 3)
    expect(inBody('[data-testid="rating-after_sales"]')!.textContent).toContain('3.0 / 5')
    await rate('after_sales', 3)
    expect(inBody('[data-testid="rating-after_sales"]')!.textContent).toContain('0.0 / 5')
    wrapper.unmount()
  })

  it('edits a manufacturer keeping its ratings', async () => {
    api.updateManufacturer.mockResolvedValue(DEERE)
    const wrapper = mountTab()
    await settle()

    await wrapper.findAll('[data-testid="edit"]')[1]!.trigger('click')
    await settle()
    expect(averagePreview()).toContain('4.5')
    await rate('after_sales', 5)
    await click('save')

    expect(api.updateManufacturer).toHaveBeenCalledWith(1, {
      name: 'John Deere',
      reputation: '5.0',
      product_quality: '4.5',
      after_sales: '5.0',
      is_enabled: true,
    })
    expect(useNotificationsStore().text).toBe('Manufacturer updated.')
    wrapper.unmount()
  })

  it('requires the name', async () => {
    const wrapper = mountTab()
    await settle()

    await wrapper.find('[data-testid="new"]').trigger('click')
    await settle()
    await click('save')

    expect(api.createManufacturer).not.toHaveBeenCalled()
    expect(document.body.textContent).toContain('This field is required.')
    wrapper.unmount()
  })

  it('shows the server validation error on the name field', async () => {
    api.createManufacturer.mockRejectedValue(
      new ApiError(400, 'Bad Request', { name: ['A manufacturer with this name already exists.'] }),
    )
    const wrapper = mountTab()
    await settle()

    await wrapper.find('[data-testid="new"]').trigger('click')
    await settle()
    await typeInto('name', 'john deere')
    await click('save')

    expect(document.body.textContent).toContain('A manufacturer with this name already exists.')
    wrapper.unmount()
  })

  it('deletes after confirmation and reloads', async () => {
    api.deleteManufacturer.mockResolvedValue(undefined)
    const wrapper = mountTab()
    await settle()
    api.listManufacturers.mockClear()

    await wrapper.findAll('[data-testid="delete"]')[0]!.trigger('click')
    await settle()
    expect(document.body.textContent).toContain('Delete "Acme"?')
    await click('confirm-button')

    expect(api.deleteManufacturer).toHaveBeenCalledWith(2)
    expect(api.listManufacturers).toHaveBeenCalledTimes(1)
    expect(useNotificationsStore().text).toBe('Manufacturer deleted.')
    wrapper.unmount()
  })
})
