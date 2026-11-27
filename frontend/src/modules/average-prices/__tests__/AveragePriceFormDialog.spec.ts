import { createPinia, setActivePinia } from 'pinia'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { defineComponent, h, ref } from 'vue'

import { setLanguage } from '@/i18n'
import * as assetClassesApi from '@/modules/catalogs/asset-classes/api'
import * as manufacturersApi from '@/modules/catalogs/manufacturers/api'
import { inBody, mountWithPlugins, openDropdown, settle } from '@/test-utils'
import AveragePriceFormDialog from '../AveragePriceFormDialog.vue'

vi.mock('@/modules/catalogs/asset-classes/api', () => ({
  listAssetClasses: vi.fn<typeof assetClassesApi.listAssetClasses>(),
  getAssetClass: vi.fn<typeof assetClassesApi.getAssetClass>(),
}))
vi.mock('@/modules/catalogs/manufacturers/api', () => ({
  listManufacturers: vi.fn<typeof manufacturersApi.listManufacturers>(),
}))

const assetClasses = vi.mocked(assetClassesApi)
const manufacturers = vi.mocked(manufacturersApi)
const page = <T>(results: T[]) => ({ count: results.length, next: null, previous: null, results })

/** The form opened as a new price (it reads its props when it opens). */
async function openForm(props: Record<string, unknown>) {
  const open = ref(false)
  mountWithPlugins(
    defineComponent({
      setup: () => () =>
        h(AveragePriceFormDialog, {
          modelValue: open.value,
          'onUpdate:modelValue': (v: boolean) => (open.value = v),
          source: null,
          ...props,
        }),
    }),
  )
  open.value = true
  await settle()
}

beforeEach(() => {
  setActivePinia(createPinia())
  setLanguage('en')
  assetClasses.listAssetClasses.mockResolvedValue(page([]))
  manufacturers.listManufacturers.mockResolvedValue(page([]))
})

afterEach(() => {
  document.body.innerHTML = ''
  vi.clearAllMocks()
})

describe('AveragePriceFormDialog opened from an eFMV analysis', () => {
  it("offers only the asset classes of the analysis's vertical, with the model typed", async () => {
    await openForm({ initialModel: ' P9999 ', scopeVertical: 1 })
    await openDropdown('asset-class')
    expect(assetClasses.listAssetClasses).toHaveBeenCalled()
    for (const [params] of assetClasses.listAssetClasses.mock.calls) {
      expect(params.filters).toEqual({ is_enabled: true, vertical: 1 })
    }
    expect((inBody('[data-testid="model"] input') as HTMLInputElement).value).toBe('P9999')
  })

  it('narrows them to its sub-vertical when it has one', async () => {
    await openForm({ scopeVertical: 1, scopeSubVertical: 11 })
    expect(assetClasses.listAssetClasses).toHaveBeenLastCalledWith(
      expect.objectContaining({ filters: { is_enabled: true, vertical: 1, sub_vertical: 11 } }),
    )
  })

  it('offers every enabled asset class otherwise (Average Prices)', async () => {
    await openForm({})
    expect(assetClasses.listAssetClasses).toHaveBeenLastCalledWith(
      expect.objectContaining({ filters: { is_enabled: true } }),
    )
  })
})
