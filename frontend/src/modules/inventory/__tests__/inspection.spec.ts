import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { i18n, setLanguage } from '@/i18n'
import KitChecklistField from '@/modules/catalogs/asset-models/KitChecklistField.vue'
import type { KitItem } from '@/modules/catalogs/asset-models/api'
import vuetify from '@/plugins/vuetify'
import { useAuthStore, type User } from '@/stores/auth'
import { click, inBody, mountWithPlugins, settle } from '@/test-utils'
import * as inventoryApi from '../api'
import ReportView from '../ReportView.vue'

vi.mock('../api', async (importOriginal) => ({
  ...(await importOriginal<typeof import('../api')>()),
  getReport: vi.fn<typeof inventoryApi.getReport>(),
  approveReport: vi.fn<typeof inventoryApi.approveReport>(),
  updateReport: vi.fn<typeof inventoryApi.updateReport>(),
  listGradeLevels: vi.fn<typeof inventoryApi.listGradeLevels>(),
}))

const api = vi.mocked(inventoryApi)

function signIn(id: number, roles: string[]) {
  useAuthStore().user = {
    id,
    is_admin: false,
    role_refs: roles.map((key) => ({ key, name: key, is_system: true })),
  } as unknown as User
}

const REPORT = {
  id: 9,
  asset: 1,
  asset_code: 'H000000018',
  asset_model_label: 'Dell Latitude 5440',
  version: 1,
  is_current: false,
  status: 'awaiting_approval',
  technician: 5,
  technician_name: 'Tina',
  grade: 'B1C',
  conservation: 'B',
  functioning: '1',
  completeness: 'C',
  recommended_destination: 'available',
  failed_components: '',
  irreparable: false,
  missing_items: [],
  checklist_done: true,
  test_results: { Boots: 'pass' },
  cleaning: 'standard',
  notes: '',
  review_notes: '',
  approved_by_name: null,
  approved_at: null,
  finished_at: '2026-11-24T10:00:00Z',
  started_at: '2026-11-24T09:00:00Z',
  sent_to_customer_at: null,
  new_version_reason: '',
  kit_checklist: [{ item: 'Battery', essential: true }],
  test_script: ['Boots'],
  has_storage: false,
  required_photo_kinds: [],
  photos: [],
  findings: [],
  erasures: [],
  lot_tool: null,
  suggestions: { functioning: '1', completeness: 'C', destination: 'available' },
  problems: [],
  asset_detail: {
    horizon_id: 'H000000018',
    serial: 'ABC1234',
    serial_status: 'captured',
    specs: [],
    asset_model_detail: { manufacturer_name: 'Dell', name: 'Latitude 5440', asset_class_name: 'Notebook', asset_class: 2 },
  },
} as unknown as inventoryApi.InspectionReport // prettier-ignore

describe('report page', () => {
  beforeEach(() => {
    setLanguage('en')
    setActivePinia(createPinia())
    api.getReport.mockResolvedValue(REPORT)
    api.listGradeLevels.mockResolvedValue([])
  })

  afterEach(() => {
    vi.clearAllMocks()
    document.body.innerHTML = ''
  })

  it('shows the report as a document with its grade; a supervisor approves it', async () => {
    signIn(7, ['inventory_supervisor'])
    api.approveReport.mockResolvedValue({ ...REPORT, status: 'approved', is_current: true })
    const wrapper = mountWithPlugins(ReportView)
    await wrapper.setProps({ id: 9 })
    await settle()
    expect(wrapper.find('[data-testid="grade"]').text()).toContain('B1C')
    expect(wrapper.find('[data-testid="report-sheet"]').text()).toContain('Battery')
    await click('approve')
    expect(api.approveReport).toHaveBeenCalledWith(9)
    expect(wrapper.find('[data-testid="approve"]').exists()).toBe(false)
    wrapper.unmount()
  })

  it('a technician cannot approve', async () => {
    signIn(5, ['inspection_technician'])
    const wrapper = mountWithPlugins(ReportView)
    await wrapper.setProps({ id: 9 })
    await settle()
    expect(wrapper.find('[data-testid="approve"]').exists()).toBe(false)
    wrapper.unmount()
  })

  it('a draft opens the step-by-step inspection, submitting only when nothing is missing', async () => {
    signIn(5, ['inspection_technician'])
    api.getReport.mockResolvedValue({
      ...REPORT,
      status: 'draft',
      grade: '',
      conservation: '',
      problems: ['Grade the conservation.'],
    })
    const wrapper = mountWithPlugins(ReportView)
    await wrapper.setProps({ id: 9 })
    await settle()
    expect(wrapper.find('[data-testid="steps"]').exists()).toBe(true)
    await click('step-classification')
    expect(inBody('[data-testid="problems"]')!.textContent).toContain('Grade the conservation.')
    expect((inBody('[data-testid="submit-report"]') as HTMLButtonElement).disabled).toBe(true)
    wrapper.unmount()
  })
})

describe('kit checklist field', () => {
  it('adds items and marks one essential', async () => {
    setLanguage('en')
    const wrapper = mount(KitChecklistField, {
      attachTo: document.body,
      global: { plugins: [vuetify, i18n] },
      props: {
        label: 'Kit',
        modelValue: [] as KitItem[],
        'onUpdate:modelValue': (value: KitItem[]) => wrapper.setProps({ modelValue: value }),
      },
    })
    const input = wrapper.find('[data-testid="kit-input"] input')
    await input.setValue('Charger, Battery')
    await input.trigger('keydown', { key: 'Enter' })
    await settle()
    expect(wrapper.props('modelValue')).toEqual([
      { item: 'Charger', essential: false },
      { item: 'Battery', essential: false },
    ])
    await wrapper.findAll('[data-testid="kit-essential"]')[1]!.trigger('click')
    expect(wrapper.props('modelValue')[1]).toEqual({ item: 'Battery', essential: true })
    wrapper.unmount()
  })
})
