import { createPinia, setActivePinia } from 'pinia'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { h } from 'vue'

import { setLanguage } from '@/i18n'
import { inBody, mountWithPlugins, settle } from '@/test-utils'
import * as pricesApi from '../api'
import PriceDocuments from '../PriceDocuments.vue'

vi.mock('../api', async (importOriginal) => ({
  ...(await importOriginal<typeof import('../api')>()),
  listPriceDocuments: vi.fn<typeof pricesApi.listPriceDocuments>(),
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

function mountDocs() {
  return mountWithPlugins({ render: () => h(PriceDocuments, { rowId: 100 }) })
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
    const wrapper = mountDocs()
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

  it('only opens and downloads: documents are changed in the form', async () => {
    const wrapper = mountDocs()
    await settle()
    expect(inBody('[data-testid="documents-add"]')).toBeNull()
    expect(inBody('[data-testid="document-delete"]')).toBeNull()
    expect(inBody('[data-testid="document-download"]')).not.toBeNull()
    wrapper.unmount()
  })
})
