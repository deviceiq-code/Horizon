import { createPinia, setActivePinia } from 'pinia'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { h, ref } from 'vue'

import { ApiError } from '@/api'
import { setLanguage } from '@/i18n'
import { click, inBody, mountWithPlugins, settle, typeInto } from '@/test-utils'
import * as pricesApi from '../api'
import PhotoSearchDialog from '../PhotoSearchDialog.vue'
import PhotoUrlDialog from '../PhotoUrlDialog.vue'

vi.mock('../api', async (importOriginal) => ({
  ...(await importOriginal<typeof import('../api')>()),
  getPhotoSuggestions: vi.fn<typeof pricesApi.getPhotoSuggestions>(),
  setPhotoFromUrl: vi.fn<typeof pricesApi.setPhotoFromUrl>(),
}))
const api = vi.mocked(pricesApi)

const FRONT: pricesApi.PhotoSuggestion = {
  image: 'https://www.deere.com/5060e.jpg',
  thumbnail: 'https://thumbs.example.com/5060e.jpg',
  title: 'John Deere 5060E',
  source: 'https://www.deere.com/tractors/5060e',
  resolution: '1366 x 768',
}
const SIDE: pricesApi.PhotoSuggestion = {
  ...FRONT,
  image: 'https://dealer.example.com/side.png',
  thumbnail: 'https://dealer.example.com/side-small.png',
  source: '',
  resolution: '',
}

function mountDialog(component: typeof PhotoSearchDialog | typeof PhotoUrlDialog) {
  const open = ref(true)
  const onChosen = vi.fn<(photoId: number) => void>()
  const wrapper = mountWithPlugins({
    render: () =>
      h(component, {
        modelValue: open.value,
        'onUpdate:modelValue': (v: boolean) => (open.value = v),
        rowId: 6,
        onChosen,
      }),
  })
  return { wrapper, open, onChosen }
}

describe('PhotoSearchDialog', () => {
  beforeEach(() => {
    setLanguage('en')
    setActivePinia(createPinia())
    api.getPhotoSuggestions.mockResolvedValue({
      query: 'John Deere 5060E Utility Tractor',
      results: [FRONT, SIDE],
    })
  })

  afterEach(() => {
    vi.clearAllMocks()
    document.body.innerHTML = ''
  })

  it('searches for the asset, then uses the image picked', async () => {
    api.setPhotoFromUrl.mockResolvedValue({ photo_id: 40 })
    const { wrapper, open, onChosen } = mountDialog(PhotoSearchDialog)
    await settle()

    // The default search comes from the API (manufacturer + model + asset class)
    expect(api.getPhotoSuggestions).toHaveBeenCalledWith(6, undefined)
    const query = inBody('[data-testid="photo-search-query"] input') as HTMLInputElement
    expect(query.value).toBe('John Deere 5060E Utility Tractor')
    const results = document.body.querySelectorAll<HTMLElement>('[data-testid="photo-result"]')
    expect(results).toHaveLength(2)
    expect(results[0]!.querySelector('img')!.getAttribute('src')).toBe(FRONT.thumbnail)
    expect(results[0]!.textContent).toMatch(/deere\.com\s+· 1366 x 768/)
    expect(results[1]!.textContent).toContain('dealer.example.com')

    expect(inBody('[data-testid="photo-use"]')!.hasAttribute('disabled')).toBe(true)
    results[0]!.click()
    await settle()
    await click('photo-use')

    expect(api.setPhotoFromUrl).toHaveBeenCalledWith(6, FRONT.image, FRONT.source)
    expect(onChosen).toHaveBeenCalledWith(40)
    expect(open.value).toBe(false)
    wrapper.unmount()
  })

  it('searches again with other words', async () => {
    const { wrapper } = mountDialog(PhotoSearchDialog)
    await settle()
    await typeInto('photo-search-query', 'deere 5060e cab')
    inBody('[data-testid="photo-search-query"]')!
      .closest('form')!
      .dispatchEvent(new Event('submit', { cancelable: true }))
    await settle()
    expect(api.getPhotoSuggestions).toHaveBeenLastCalledWith(6, 'deere 5060e cab')
    wrapper.unmount()
  })

  it('keeps the dialog open when the site refuses the download', async () => {
    api.setPhotoFromUrl.mockRejectedValue(
      new ApiError(400, 'Bad Request', { url: ['The site answered with an error.'] }),
    )
    const { wrapper, open, onChosen } = mountDialog(PhotoSearchDialog)
    await settle()
    document.body.querySelector<HTMLElement>('[data-testid="photo-result"]')!.click()
    await settle()
    await click('photo-use')

    expect(inBody('[data-testid="photo-save-error"]')!.textContent).toContain(
      'The site answered with an error.',
    )
    expect(open.value).toBe(true)
    expect(onChosen).not.toHaveBeenCalled()
    wrapper.unmount()
  })

  it('shows why the search failed', async () => {
    api.getPhotoSuggestions.mockRejectedValue(
      new ApiError(502, 'SearXNG refused the JSON format.', { detail: '…' }),
    )
    const { wrapper } = mountDialog(PhotoSearchDialog)
    await settle()
    expect(inBody('[data-testid="photo-search-error"]')!.textContent).toContain(
      'SearXNG refused the JSON format.',
    )
    wrapper.unmount()
  })
})

describe('PhotoUrlDialog', () => {
  beforeEach(() => {
    setLanguage('en')
    setActivePinia(createPinia())
  })

  afterEach(() => {
    vi.clearAllMocks()
    document.body.innerHTML = ''
  })

  it('downloads the image at the address pasted', async () => {
    api.setPhotoFromUrl.mockResolvedValue({ photo_id: 41 })
    const { wrapper, open, onChosen } = mountDialog(PhotoUrlDialog)
    await settle()
    await typeInto('photo-url', ' https://example.com/5060e.jpg ')
    await click('photo-url-save')

    expect(api.setPhotoFromUrl).toHaveBeenCalledWith(6, 'https://example.com/5060e.jpg')
    expect(onChosen).toHaveBeenCalledWith(41)
    expect(open.value).toBe(false)
    wrapper.unmount()
  })

  it('shows the reason an address is refused', async () => {
    api.setPhotoFromUrl.mockRejectedValue(
      new ApiError(400, 'Bad Request', {
        url: ['Addresses on the local network are not allowed.'],
      }),
    )
    const { wrapper, open } = mountDialog(PhotoUrlDialog)
    await settle()
    await typeInto('photo-url', 'http://192.168.0.10/a.jpg')
    await click('photo-url-save')

    expect(inBody('[data-testid="photo-url"]')!.textContent).toContain(
      'Addresses on the local network are not allowed.',
    )
    expect(open.value).toBe(true)
    wrapper.unmount()
  })
})
