import { createPinia, setActivePinia } from 'pinia'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { h, ref } from 'vue'

import { setLanguage } from '@/i18n'
import { useNotificationsStore } from '@/stores/notifications'
import { useSystemSettingsStore } from '@/stores/systemSettings'
import { inBody, mountWithPlugins, settle } from '@/test-utils'
import * as pricesApi from '../api'
import PricePhoto from '../PricePhoto.vue'

vi.mock('../api', async (importOriginal) => ({
  ...(await importOriginal<typeof import('../api')>()),
  uploadPricePhoto: vi.fn<typeof pricesApi.uploadPricePhoto>(),
  deletePricePhoto: vi.fn<typeof pricesApi.deletePricePhoto>(),
}))
const api = vi.mocked(pricesApi)

function mountPhoto(photoId: number | null, canEdit = true) {
  const current = ref(photoId)
  const wrapper = mountWithPlugins({
    render: () =>
      h(PricePhoto, {
        rowId: 100,
        photoId: current.value,
        icon: 'mdi-excavator',
        title: 'Caterpillar 320 GC',
        canEdit,
        onChanged: (id: number | null) => (current.value = id),
      }),
  })
  return { wrapper, current }
}

describe('PricePhoto', () => {
  beforeEach(() => {
    setLanguage('en')
    setActivePinia(createPinia())
    useSystemSettingsStore().settings = { photo_search_enabled: false }
  })

  afterEach(() => {
    vi.clearAllMocks()
    document.body.innerHTML = ''
  })

  it('shows the icon without a photo and uploads one', async () => {
    api.uploadPricePhoto.mockResolvedValue({ photo_id: 31 })
    const { wrapper, current } = mountPhoto(null)
    await settle()
    expect(inBody('.mdi-excavator')).not.toBeNull()
    expect(inBody('[data-testid="photo-upload"]')!.getAttribute('title')).toBe('Add photo')

    const file = new File(['jpeg'], 'front.jpg', { type: 'image/jpeg' })
    const input = inBody('[data-testid="photo-input"]') as HTMLInputElement
    Object.defineProperty(input, 'files', { value: [file], configurable: true })
    input.dispatchEvent(new Event('change'))
    await settle()

    expect(api.uploadPricePhoto).toHaveBeenCalledWith(100, file)
    expect(current.value).toBe(31)
    expect(useNotificationsStore().text).toBe('Photo saved.')
    expect(inBody('[data-testid="photo-thumb"] img')!.getAttribute('src')).toBe(
      '/api/average-prices/100/photo/?v=31',
    )
    // The whole photo fits in the square (contain), it is never cropped (cover)
    expect(inBody('[data-testid="photo-thumb"] .v-img__img--contain')).not.toBeNull()
    expect(inBody('[data-testid="photo-thumb"] .v-img__img--cover')).toBeNull()
    wrapper.unmount()
  })

  it('enlarges the photo and removes it after confirmation', async () => {
    api.deletePricePhoto.mockResolvedValue(undefined)
    const { wrapper, current } = mountPhoto(31)
    await settle()

    inBody('[data-testid="photo-thumb"]')!.click()
    await settle()
    expect(inBody('[data-testid="photo-large"]')).not.toBeNull()

    inBody('[data-testid="photo-remove"]')!.click()
    await settle()
    inBody('.v-overlay--active [data-testid="confirm-button"]')!.click()
    await settle()
    expect(api.deletePricePhoto).toHaveBeenCalledWith(100)
    expect(current.value).toBeNull()
    wrapper.unmount()
  })

  it('cannot be changed on a deleted price', async () => {
    const { wrapper } = mountPhoto(31, false)
    await settle()
    expect(inBody('[data-testid="photo-upload"]')).toBeNull()
    expect(inBody('[data-testid="photo-remove"]')).toBeNull()
    wrapper.unmount()
  })

  it('offers a file, the address of an image and (when set up) a search', async () => {
    const { wrapper } = mountPhoto(null)
    await settle()
    inBody('[data-testid="photo-upload"]')!.click()
    await settle()
    expect(inBody('[data-testid="photo-from-file"]')).not.toBeNull()
    expect(inBody('[data-testid="photo-from-url"]')).not.toBeNull()
    expect(inBody('[data-testid="photo-from-search"]')).toBeNull()
    wrapper.unmount()
    document.body.innerHTML = ''

    useSystemSettingsStore().settings = { photo_search_enabled: true }
    const second = mountPhoto(null)
    await settle()
    inBody('[data-testid="photo-upload"]')!.click()
    await settle()
    expect(inBody('[data-testid="photo-from-search"]')).not.toBeNull()
    second.wrapper.unmount()
  })

  it('links to where the photo was found', async () => {
    const wrapper = mountWithPlugins({
      render: () =>
        h(PricePhoto, {
          rowId: 100,
          photoId: 31,
          icon: 'mdi-excavator',
          title: 'Caterpillar 320 GC',
          canEdit: true,
          sourceUrl: 'https://www.cat.com/320',
        }),
    })
    await settle()
    inBody('[data-testid="photo-thumb"]')!.click()
    await settle()
    const link = inBody('[data-testid="photo-source"]') as HTMLAnchorElement
    expect(link.getAttribute('href')).toBe('https://www.cat.com/320')
    expect(link.getAttribute('target')).toBe('_blank')
    wrapper.unmount()
  })
})
