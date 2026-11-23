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

function mountDialog(component: 'search' | 'url') {
  const open = ref(true)
  const onChosen = vi.fn<(...args: string[]) => void>()
  const props = {
    modelValue: open.value,
    'onUpdate:modelValue': (v: boolean) => (open.value = v),
    onChosen,
  }
  const wrapper = mountWithPlugins({
    render: () =>
      component === 'search'
        ? h(PhotoSearchDialog, {
            ...props,
            modelValue: open.value,
            initialQuery: 'John Deere 5060E Utility Tractor',
          })
        : h(PhotoUrlDialog, { ...props, modelValue: open.value }),
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

  it('searches for the asset, then gives the image picked back to the form', async () => {
    const { wrapper, open, onChosen } = mountDialog('search')
    await settle()

    // The search the form gives (manufacturer + model + asset class)
    expect(api.getPhotoSuggestions).toHaveBeenCalledWith('John Deere 5060E Utility Tractor')
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

    // Downloaded by the server only when the form is saved
    expect(onChosen).toHaveBeenCalledWith(FRONT.image, FRONT.source)
    expect(open.value).toBe(false)
    wrapper.unmount()
  })

  it('searches again with other words', async () => {
    const { wrapper } = mountDialog('search')
    await settle()
    await typeInto('photo-search-query', 'deere 5060e cab')
    inBody('[data-testid="photo-search-query"]')!
      .closest('form')!
      .dispatchEvent(new Event('submit', { cancelable: true }))
    await settle()
    expect(api.getPhotoSuggestions).toHaveBeenLastCalledWith('deere 5060e cab')
    wrapper.unmount()
  })

  it('shows why the search failed', async () => {
    api.getPhotoSuggestions.mockRejectedValue(
      new ApiError(502, 'SearXNG refused the JSON format.', { detail: '…' }),
    )
    const { wrapper } = mountDialog('search')
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

  it('gives the address pasted back to the form', async () => {
    const { wrapper, open, onChosen } = mountDialog('url')
    await settle()
    await typeInto('photo-url', ' https://example.com/5060e.jpg ')
    await click('photo-url-save')

    expect(onChosen).toHaveBeenCalledWith('https://example.com/5060e.jpg')
    expect(open.value).toBe(false)
    wrapper.unmount()
  })

  it('refuses what is not a web address', async () => {
    const { wrapper, open, onChosen } = mountDialog('url')
    await settle()
    await typeInto('photo-url', 'ftp://example.com/a.jpg')
    await click('photo-url-save')

    expect(inBody('[data-testid="photo-url"]')!.textContent).toContain(
      'Enter the address of an image (http or https).',
    )
    expect(onChosen).not.toHaveBeenCalled()
    expect(open.value).toBe(true)
    wrapper.unmount()
  })
})
