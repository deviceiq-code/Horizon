import { createPinia, setActivePinia } from 'pinia'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { setLanguage } from '@/i18n'
import * as assetClassesApi from '@/modules/catalogs/asset-classes/api'
import * as manufacturersApi from '@/modules/catalogs/manufacturers/api'
import { useNotificationsStore } from '@/stores/notifications'
import { click, inBody, mountWithPlugins, pickOption, settle, typeInto } from '@/test-utils'
import * as modelsApi from '../asset-models/api'
import AssetModelsTab from '../asset-models/AssetModelsTab.vue'

vi.mock('../asset-models/api', () => ({
  listAssetModels: vi.fn<typeof modelsApi.listAssetModels>(),
  createAssetModel: vi.fn<typeof modelsApi.createAssetModel>(),
  updateAssetModel: vi.fn<typeof modelsApi.updateAssetModel>(),
  deleteAssetModel: vi.fn<typeof modelsApi.deleteAssetModel>(),
}))
vi.mock('@/modules/catalogs/asset-classes/api', () => ({
  listAssetClasses: vi.fn<typeof assetClassesApi.listAssetClasses>(),
  getAssetClass: vi.fn<typeof assetClassesApi.getAssetClass>(),
}))
vi.mock('@/modules/catalogs/manufacturers/api', () => ({
  listManufacturers: vi.fn<typeof manufacturersApi.listManufacturers>(),
}))
vi.mock('@/modules/average-prices/api', () => ({
  getSpecSuggestions: vi.fn<() => Promise<string[]>>(),
}))

const api = vi.mocked(modelsApi)
const classes = vi.mocked(assetClassesApi)
const manufacturers = vi.mocked(manufacturersApi)
const page = <T>(results: T[]) => ({ count: results.length, next: null, previous: null, results })

const RAM = {
  key: 'ram_gb',
  label: 'RAM',
  kind: 'number' as const,
  unit: 'GB',
  required: true,
  options: [],
}

const NOTEBOOK = {
  id: 5,
  name: 'Notebook',
  icon: 'mdi-laptop',
  sub_vertical_detail: { label: 'IT / General', vertical: { is_enabled: true } },
  spec_template: [RAM],
} as unknown as assetClassesApi.AssetClass

const LATITUDE: modelsApi.AssetModel = {
  id: 1,
  manufacturer: 7,
  manufacturer_name: 'Dell',
  name: 'Latitude 5440',
  asset_class: 5,
  asset_class_detail: { id: 5, name: 'Notebook', icon: 'mdi-laptop', has_template: true },
  spec_values: [{ ...RAM, value: '16' }],
  tracking: 'unit',
  serial_regex: '',
  kit_checklist: ['Charger'],
  test_script: [],
  has_storage: true,
  keywords: [],
  notes: '',
  is_enabled: true,
  assets_count: 3,
  created_at: '',
  updated_at: '',
}

describe('AssetModelsTab', () => {
  beforeEach(() => {
    setLanguage('en')
    setActivePinia(createPinia())
    api.listAssetModels.mockResolvedValue(page([LATITUDE]))
    classes.listAssetClasses.mockResolvedValue(page([NOTEBOOK]))
    classes.getAssetClass.mockResolvedValue(NOTEBOOK)
    manufacturers.listManufacturers.mockResolvedValue(
      page([{ id: 7, name: 'Dell' } as manufacturersApi.Manufacturer]),
    )
  })

  afterEach(() => {
    vi.clearAllMocks()
    document.body.innerHTML = ''
  })

  it('lists models with their manufacturer, specifications, tracking and storage', async () => {
    const wrapper = mountWithPlugins(AssetModelsTab)
    await settle()
    const row = wrapper.find('tbody tr').text()
    expect(row).toContain('Dell')
    expect(row).toContain('Latitude 5440')
    expect(row).toContain('16 GB')
    expect(row).toContain('By Unit')
    expect(row).toContain('Storage')
    wrapper.unmount()
  })

  it('creates a model with the class specification values, none required', async () => {
    api.createAssetModel.mockResolvedValue({ ...LATITUDE, id: 2 })
    const wrapper = mountWithPlugins(AssetModelsTab)
    await settle()
    await click('new')
    expect(inBody('[data-testid="no-template"]')).not.toBeNull()
    await pickOption('manufacturer', 'Dell')
    await typeInto('name', 'Latitude 7450')
    await pickOption('asset-class', 'Notebook — IT / General')
    // RAM is required for assets, not for the model: saving with it empty works
    await click('save')
    expect(api.createAssetModel).toHaveBeenLastCalledWith(
      expect.objectContaining({
        manufacturer: 7,
        name: 'Latitude 7450',
        asset_class: 5,
        specs: { ram_gb: '' },
        tracking: 'unit',
      }),
    )
    expect(useNotificationsStore().text).toBe('Asset model created.')
    wrapper.unmount()
  })
})
