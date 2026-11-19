import { createPinia, setActivePinia } from 'pinia'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { h } from 'vue'

import { ApiError } from '@/api'
import { setLanguage } from '@/i18n'
import { useNotificationsStore } from '@/stores/notifications'
import { inBody, mountWithPlugins, settle } from '@/test-utils'
import * as pricesApi from '../api'
import PriceDocuments from '../PriceDocuments.vue'

vi.mock('../api', async (importOriginal) => ({
  ...(await importOriginal<typeof import('../api')>()),
  listPriceDocuments: vi.fn<typeof pricesApi.listPriceDocuments>(),
  uploadPriceDocument: vi.fn<typeof pricesApi.uploadPriceDocument>(),
  deletePriceDocument: vi.fn<typeof pricesApi.deletePriceDocument>(),
}))
const api = vi.mocked(pricesApi)

const CATALOG: pricesApi.PriceDocument = {
  id: 7,
  name: 'Catalog 2026.pdf',
  size: 2.5 * 1024 * 1024,
  content_type: 'application/pdf',
  opens_inline: true,
  uploaded_at: '2026-11-19T15:00:00Z',
  uploaded_by_name: 'Ana Souza',
}
const SHEET: pricesApi.PriceDocument = {
  ...CATALOG,
  id: 8,
  name: 'Specs.xlsx',
  size: 800,
  content_type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
  opens_inline: false,
}

function mountDocs(canEdit = true) {
  const onChanged = vi.fn<(count: number) => void>()
  const wrapper = mountWithPlugins({
    render: () => h(PriceDocuments, { rowId: 100, canEdit, onChanged }),
  })
  return { wrapper, onChanged }
}

async function chooseFiles(files: File[]) {
  const input = inBody('[data-testid="documents-input"]') as HTMLInputElement
  Object.defineProperty(input, 'files', { value: files, configurable: true })
  input.dispatchEvent(new Event('change'))
  await settle()
}

describe('PriceDocuments', () => {
  beforeEach(() => {
    setLanguage('en')
    setActivePinia(createPinia())
    api.listPriceDocuments.mockResolvedValue([CATALOG, SHEET])
  })

  afterEach(() => {
    vi.clearAllMocks()
    document.body.innerHTML = ''
  })

  it('lists documents: PDFs open in a tab, other files download', async () => {
    const { wrapper } = mountDocs()
    await settle()

    expect(api.listPriceDocuments).toHaveBeenCalledWith(100)
    const items = document.body.querySelectorAll<HTMLAnchorElement>('[data-testid="document-item"]')
    expect(items).toHaveLength(2)
    expect(items[0]!.textContent).toContain('Catalog 2026.pdf')
    expect(items[0]!.textContent).toContain('2.5 MB')
    expect(items[0]!.textContent).toContain('Ana Souza')
    expect(items[0]!.getAttribute('href')).toBe(
      '/api/average-prices/100/documents/7/download/?inline=1',
    )
    expect(items[0]!.getAttribute('target')).toBe('_blank')
    expect(items[1]!.getAttribute('href')).toBe('/api/average-prices/100/documents/8/download/')
    expect(items[1]!.getAttribute('target')).toBeNull()
    expect(items[1]!.textContent).toContain('0.8 kB')
    wrapper.unmount()
  })

  it('uploads several files, reporting the ones refused', async () => {
    api.uploadPriceDocument
      .mockResolvedValueOnce(CATALOG)
      .mockRejectedValueOnce(
        new ApiError(400, 'Bad Request', { file: ['This type of file is not accepted.'] }),
      )
    const { wrapper, onChanged } = mountDocs()
    await settle()

    const good = new File(['%PDF'], 'Brochure.pdf')
    const bad = new File(['MZ'], 'tool.exe')
    await chooseFiles([good, bad])

    expect(api.uploadPriceDocument).toHaveBeenNthCalledWith(1, 100, good)
    expect(api.uploadPriceDocument).toHaveBeenNthCalledWith(2, 100, bad)
    expect(useNotificationsStore().text).toBe('Document added.')
    expect(api.listPriceDocuments).toHaveBeenCalledTimes(2) // reloaded
    expect(onChanged).toHaveBeenCalledWith(2)
    wrapper.unmount()
  })

  it('reports a refused file by name', async () => {
    api.uploadPriceDocument.mockRejectedValue(
      new ApiError(400, 'Bad Request', { file: ['The file is too large (maximum 25 MB).'] }),
    )
    const { wrapper, onChanged } = mountDocs()
    await settle()
    await chooseFiles([new File(['x'], 'huge.pdf')])

    expect(useNotificationsStore().text).toBe('huge.pdf: The file is too large (maximum 25 MB).')
    expect(onChanged).not.toHaveBeenCalled()
    wrapper.unmount()
  })

  it('deletes a document after confirmation', async () => {
    api.deletePriceDocument.mockResolvedValue(undefined)
    const { wrapper, onChanged } = mountDocs()
    await settle()

    api.listPriceDocuments.mockResolvedValue([SHEET])
    inBody('[data-testid="document-delete"]')!.click()
    await settle()
    expect(document.body.textContent).toContain('Delete "Catalog 2026.pdf"?')
    inBody('.v-overlay--active [data-testid="confirm-button"]')!.click()
    await settle()

    expect(api.deletePriceDocument).toHaveBeenCalledWith(100, 7)
    expect(onChanged).toHaveBeenCalledWith(1)
    expect(document.body.querySelectorAll('[data-testid="document-item"]')).toHaveLength(1)
    wrapper.unmount()
  })

  it('a deleted price only lets documents be opened', async () => {
    const { wrapper } = mountDocs(false)
    await settle()
    expect(inBody('[data-testid="documents-add"]')).toBeNull()
    expect(inBody('[data-testid="document-delete"]')).toBeNull()
    expect(inBody('[data-testid="document-download"]')).not.toBeNull()
    wrapper.unmount()
  })
})
