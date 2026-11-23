import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { ApiError } from '@/api'
import { i18n, setLanguage } from '@/i18n'
import * as modelsApi from '@/modules/catalogs/asset-models/api'
import vuetify from '@/plugins/vuetify'
import { useAuthStore, type User } from '@/stores/auth'
import { click, inBody, mountWithPlugins, pickOption, settle, typeInto } from '@/test-utils'
import * as inventoryApi from '../api'
import ExpectedItemsEditor from '../ExpectedItemsEditor.vue'
import type { EditorRow } from '../expectedRows'
import * as labels from '../labels'
import LotView from '../LotView.vue'
import TriagePanel from '../TriagePanel.vue'

vi.mock('../api', async (importOriginal) => ({
  ...(await importOriginal<typeof import('../api')>()),
  triageUnit: vi.fn<typeof inventoryApi.triageUnit>(),
  parseExpected: vi.fn<typeof inventoryApi.parseExpected>(),
  getLot: vi.fn<typeof inventoryApi.getLot>(),
  lotReceived: vi.fn<typeof inventoryApi.lotReceived>(),
  lotExpected: vi.fn<typeof inventoryApi.lotExpected>(),
  listOccurrences: vi.fn<typeof inventoryApi.listOccurrences>(),
  listLotAttachments: vi.fn<typeof inventoryApi.listLotAttachments>(),
}))
vi.mock('@/modules/catalogs/asset-models/api', () => ({
  listAssetModels: vi.fn<typeof modelsApi.listAssetModels>(),
}))
vi.mock('../labels', async (importOriginal) => ({
  ...(await importOriginal<typeof import('../labels')>()),
  printLabels: vi.fn<typeof labels.printLabels>(),
}))

const api = vi.mocked(inventoryApi)
const models = vi.mocked(modelsApi)
const print = vi.mocked(labels.printLabels)
const page = <T>(results: T[]) => ({ count: results.length, next: null, previous: null, results })

const LATITUDE = {
  id: 3,
  manufacturer_name: 'Dell',
  name: 'Latitude 5440',
  asset_class_detail: { name: 'Notebook' },
  tracking: 'unit',
  serial_regex: '',
} as unknown as modelsApi.AssetModel

const LOT = {
  id: 5,
  code: 'LOT-2026-0001',
  status: 'open',
  customer_name: 'TransRápido',
  warehouse_detail: { id: 1, code: 'SP01', name: 'Garantia' },
  dock_detail: { id: 2, code: 'SP01-DOC', area_type: 'dock' },
  appointment: 9,
  appointment_detail: { id: 9, code: 'APT-2026-0001' },
  fiscal_document_number: '',
  is_scheduled: true,
  units_count: 0,
  open_occurrences: 0,
  opened_at: '2026-11-24T10:00:00Z',
  opened_by_name: 'Rita',
  closed_at: null,
} as unknown as inventoryApi.Lot

function signIn(roles: string[]) {
  useAuthStore().user = {
    id: 1,
    username: 'u',
    is_admin: false,
    roles: [],
    role_refs: roles.map((key) => ({ key, name: key, is_system: true })),
  } as unknown as User
}

describe('triage (blind count)', () => {
  beforeEach(() => {
    setLanguage('en')
    setActivePinia(createPinia())
    models.listAssetModels.mockResolvedValue(page([LATITUDE]))
  })

  afterEach(() => {
    vi.clearAllMocks()
    document.body.innerHTML = ''
  })

  it('reads the serial and saves; a new ID has its label printed at once', async () => {
    api.triageUnit.mockResolvedValue({
      id: 1,
      horizon_id: 'H000000018',
      serial: 'ABC1234',
      asset_model_detail: { manufacturer_name: 'Dell', name: 'Latitude 5440' },
    } as inventoryApi.Asset)
    const wrapper = mountWithPlugins(TriagePanel)
    await wrapper.setProps({ lot: LOT })
    await settle()
    await pickOption('triage-model', 'Dell Latitude 5440')
    await typeInto('triage-serial', 'abc1234')
    inBody('[data-testid="triage-serial"] input')!.dispatchEvent(
      new KeyboardEvent('keydown', { key: 'Enter', bubbles: true }),
    )
    await settle()
    expect(api.triageUnit).toHaveBeenCalledWith(5, {
      asset_model: 3,
      horizon_id: '',
      serial: 'abc1234',
      no_serial_reason: '',
      container_code: '',
      photo: null,
    })
    expect(inBody('[data-testid="triage-feedback"]')!.textContent).toContain('H000000018 saved')
    expect(print).toHaveBeenCalledOnce()
    wrapper.unmount()
  })

  it('without a serial, asks for the reason and a photo before saving', async () => {
    const wrapper = mountWithPlugins(TriagePanel)
    await wrapper.setProps({ lot: LOT })
    await settle()
    await pickOption('triage-model', 'Dell Latitude 5440')
    await click('triage-save')
    expect(api.triageUnit).not.toHaveBeenCalled()
    expect(inBody('[data-testid="triage-feedback"]')!.textContent).toContain('take a photo')
    expect(inBody('[data-testid="triage-reason"]')).not.toBeNull()
    wrapper.unmount()
  })

  it('shows the server refusal (e.g. a serial already received)', async () => {
    api.triageUnit.mockRejectedValue(
      new ApiError(400, 'An asset of this model with this serial number already exists.', {
        detail: 'An asset of this model with this serial number already exists.',
        field: 'serial',
      }),
    )
    const wrapper = mountWithPlugins(TriagePanel)
    await wrapper.setProps({ lot: LOT })
    await settle()
    await pickOption('triage-model', 'Dell Latitude 5440')
    await typeInto('triage-serial', 'ABC1234')
    await click('triage-save')
    expect(inBody('[data-testid="triage-feedback"]')!.textContent).toContain('already exists')
    wrapper.unmount()
  })
})

describe('expected list editor', () => {
  beforeEach(() => {
    setLanguage('en')
    setActivePinia(createPinia())
  })

  afterEach(() => {
    vi.clearAllMocks()
    document.body.innerHTML = ''
  })

  it('imports rows pasted from a spreadsheet and flags what was not found', async () => {
    api.parseExpected.mockResolvedValue({
      rows: [
        { line: 1, asset_model: 3, asset_model_label: 'Dell Latitude 5440', tracking: 'unit', serial: 'S1', quantity: 1, errors: [] },
        { line: 2, asset_model: null, asset_model_label: 'Unknown', tracking: null, serial: '', quantity: 2, errors: ['Model not found: Unknown.'] },
      ],
    }) // prettier-ignore
    const wrapper = mount(ExpectedItemsEditor, {
      attachTo: document.body,
      global: { plugins: [vuetify, i18n] },
      props: {
        modelValue: [] as EditorRow[],
        'onUpdate:modelValue': (value: EditorRow[]) => wrapper.setProps({ modelValue: value }),
      },
    })
    await click('paste')
    await typeInto('paste-text', 'Dell Latitude 5440\tS1\nUnknown\t\t2')
    await click('paste-import')
    expect(api.parseExpected).toHaveBeenCalledWith('Dell Latitude 5440\tS1\nUnknown\t\t2')
    const shown = wrapper.findAll('[data-testid="expected-row"]')
    expect(shown).toHaveLength(2)
    expect(shown[1]!.classes()).toContain('row-error')
    expect(shown[1]!.text()).toContain('Model not found')
    expect(wrapper.find('[data-testid="expected-totals"]').text()).toContain('2 lines · 3 units')
    wrapper.unmount()
  })
})

describe('lot page', () => {
  beforeEach(() => {
    setLanguage('en')
    setActivePinia(createPinia())
    api.getLot.mockResolvedValue(LOT)
    api.lotReceived.mockResolvedValue({ units: [], accessories: [] })
    api.lotExpected.mockResolvedValue([])
    api.listOccurrences.mockResolvedValue(page([]))
    api.listLotAttachments.mockResolvedValue([])
    models.listAssetModels.mockResolvedValue(page([]))
  })

  afterEach(() => {
    vi.clearAllMocks()
    document.body.innerHTML = ''
  })

  it('a receiver triages without ever seeing the expected list (RN-17)', async () => {
    signIn(['receiver'])
    const wrapper = mountWithPlugins(LotView)
    await wrapper.setProps({ id: 5 })
    await settle()
    expect(wrapper.find('[data-testid="tab-triage"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="tab-expected"]').exists()).toBe(false)
    expect(api.lotExpected).not.toHaveBeenCalled()
    wrapper.unmount()
  })

  it('an analyst sees the expected list but does not triage', async () => {
    signIn(['remarketing_analyst'])
    const wrapper = mountWithPlugins(LotView)
    await wrapper.setProps({ id: 5 })
    await settle()
    expect(wrapper.find('[data-testid="tab-expected"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="tab-triage"]').exists()).toBe(false)
    expect(api.lotExpected).toHaveBeenCalledWith(5)
    wrapper.unmount()
  })
})
