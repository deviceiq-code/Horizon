import { createPinia, setActivePinia } from 'pinia'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { h, ref } from 'vue'

import { ApiError } from '@/api'
import { setLanguage } from '@/i18n'
import { useSystemSettingsStore } from '@/stores/systemSettings'
import { inBody, mountWithPlugins, settle } from '@/test-utils'
import * as pricesApi from '../api'
import { applyMediaChanges, hasMediaChanges, noMediaChanges, type MediaChanges } from '../media'
import PriceMediaTab from '../PriceMediaTab.vue'

vi.mock('../api', async (importOriginal) => ({
  ...(await importOriginal<typeof import('../api')>()),
  listPriceDocuments: vi.fn<typeof pricesApi.listPriceDocuments>(),
  uploadPriceDocument: vi.fn<typeof pricesApi.uploadPriceDocument>(),
  deletePriceDocument: vi.fn<typeof pricesApi.deletePriceDocument>(),
  uploadPricePhoto: vi.fn<typeof pricesApi.uploadPricePhoto>(),
  deletePricePhoto: vi.fn<typeof pricesApi.deletePricePhoto>(),
  setPhotoFromUrl: vi.fn<typeof pricesApi.setPhotoFromUrl>(),
}))
const api = vi.mocked(pricesApi)

const CATALOG: pricesApi.PriceDocument = {
  id: 7,
  name: 'Catalog 2026.pdf',
  size: 2048,
  content_type: 'application/pdf',
  opens_inline: true,
  uploaded_at: '2026-11-19T15:00:00Z',
  uploaded_by_name: 'Ana Souza',
}

function mountTab(rowId: number | null, photoId: number | null = null) {
  const changes = ref<MediaChanges>(noMediaChanges())
  const wrapper = mountWithPlugins({
    render: () =>
      h(PriceMediaTab, {
        modelValue: changes.value,
        'onUpdate:modelValue': (v: MediaChanges) => (changes.value = v),
        rowId,
        photoId,
        icon: 'mdi-monitor',
        title: 'Dell P2423H Monitor',
      }),
  })
  return { wrapper, changes }
}

async function chooseFiles(testId: string, files: File[]) {
  const input = inBody(`[data-testid="${testId}"]`) as HTMLInputElement
  Object.defineProperty(input, 'files', { value: files, configurable: true })
  input.dispatchEvent(new Event('change'))
  await settle()
}

describe('PriceMediaTab', () => {
  beforeEach(() => {
    setLanguage('en')
    setActivePinia(createPinia())
    useSystemSettingsStore().settings = {
      photo_search_enabled: false,
      user_name_display: 'full_name',
      full_name_order: 'first_last',
    }
    api.listPriceDocuments.mockResolvedValue([CATALOG])
    URL.createObjectURL = vi.fn<(object: Blob) => string>(() => 'blob:front')
    URL.revokeObjectURL = vi.fn<(url: string) => void>()
  })

  afterEach(() => {
    vi.clearAllMocks()
    document.body.innerHTML = ''
  })

  it('every change is pending: nothing is sent until the form is saved', async () => {
    const { wrapper, changes } = mountTab(100, 31)
    await settle()
    expect(inBody('[data-testid="media-tab"]')!.textContent).toContain('same in every version')
    expect(inBody('[data-testid="media-photo-image"] img')!.getAttribute('src')).toBe(
      '/api/average-prices/100/photo/?v=31',
    )
    // A new photo from a file: shown at once, pending
    const front = new File(['jpeg'], 'front.jpg', { type: 'image/jpeg' })
    await chooseFiles('photo-input', [front])
    expect(changes.value.photo).toEqual({ kind: 'file', file: front, preview: 'blob:front' })
    expect(inBody('[data-testid="photo-pending"]')).not.toBeNull()
    // Documents: one added, the saved one deleted
    const sheet = new File(['x'], 'Specs.xlsx', { type: 'application/vnd.ms-excel' })
    await chooseFiles('documents-input', [sheet])
    expect(inBody('[data-testid="document-pending"]')!.textContent).toContain('Specs.xlsx')
    inBody('[data-testid="document-delete"]')!.click()
    await settle()
    expect(changes.value).toEqual({ photo: changes.value.photo, add: [sheet], remove: [7] })
    expect(document.body.querySelectorAll('[data-testid="document-item"]')).toHaveLength(0)
    // Nothing was sent
    expect(api.uploadPricePhoto).not.toHaveBeenCalled()
    expect(api.uploadPriceDocument).not.toHaveBeenCalled()
    expect(api.deletePriceDocument).not.toHaveBeenCalled()
    // Undo the photo
    inBody('[data-testid="photo-undo"]')!.click()
    await settle()
    expect(changes.value.photo).toBeNull()
    wrapper.unmount()
  })

  it('a new price: no documents yet; removing a photo just chosen drops it', async () => {
    const { wrapper, changes } = mountTab(null)
    await settle()
    expect(api.listPriceDocuments).not.toHaveBeenCalled()
    expect(inBody('.mdi-monitor')).not.toBeNull()
    await chooseFiles('photo-input', [new File(['jpeg'], 'a.jpg', { type: 'image/jpeg' })])
    inBody('[data-testid="photo-remove"]')!.click()
    await settle()
    expect(changes.value.photo).toBeNull()
    wrapper.unmount()
  })
})

describe('applyMediaChanges', () => {
  afterEach(() => vi.clearAllMocks())

  it('applies the photo and documents to the row, reporting what was refused', async () => {
    api.setPhotoFromUrl.mockResolvedValue({ photo_id: 9 })
    api.deletePriceDocument.mockResolvedValue()
    api.uploadPriceDocument
      .mockResolvedValueOnce(CATALOG)
      .mockRejectedValueOnce(new ApiError(400, 'Bad Request', { file: ['Too big.'] }))
    const good = new File(['a'], 'a.pdf')
    const big = new File(['b'], 'big.zip')
    const changes: MediaChanges = {
      photo: { kind: 'url', url: 'https://x.com/a.jpg', source: 'https://x.com' },
      add: [good, big],
      remove: [7],
    }
    expect(hasMediaChanges(changes)).toBe(true)
    expect(hasMediaChanges(noMediaChanges())).toBe(false)
    const problems = await applyMediaChanges(100, changes)
    expect(api.setPhotoFromUrl).toHaveBeenCalledWith(100, 'https://x.com/a.jpg', 'https://x.com')
    expect(api.deletePriceDocument).toHaveBeenCalledWith(100, 7)
    expect(api.uploadPriceDocument).toHaveBeenCalledWith(100, good)
    expect(problems).toEqual([{ name: 'big.zip', reason: 'Too big.' }])
  })

  it('removes the photo', async () => {
    api.deletePricePhoto.mockResolvedValue()
    expect(await applyMediaChanges(5, { photo: { kind: 'remove' }, add: [], remove: [] })).toEqual(
      [],
    )
    expect(api.deletePricePhoto).toHaveBeenCalledWith(5)
  })
})
