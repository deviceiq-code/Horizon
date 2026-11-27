import { createPinia, setActivePinia } from 'pinia'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import AlertsMenu from '@/components/AlertsMenu.vue'
import { setLanguage } from '@/i18n'
import { useAuthStore, type User } from '@/stores/auth'
import { click, inBody, mountWithPlugins, settle } from '@/test-utils'
import * as inventoryApi from '../api'
import BlocksView from '../BlocksView.vue'
import DisputesView from '../DisputesView.vue'

vi.mock('../api', async (importOriginal) => ({
  ...(await importOriginal<typeof import('../api')>()),
  listBlocks: vi.fn<typeof inventoryApi.listBlocks>(),
  notifyBlocks: vi.fn<typeof inventoryApi.notifyBlocks>(),
  listDisputes: vi.fn<typeof inventoryApi.listDisputes>(),
  listCharges: vi.fn<typeof inventoryApi.listCharges>(),
  analyzeDispute: vi.fn<typeof inventoryApi.analyzeDispute>(),
  decideDispute: vi.fn<typeof inventoryApi.decideDispute>(),
  alertCount: vi.fn<typeof inventoryApi.alertCount>(),
  listAlerts: vi.fn<typeof inventoryApi.listAlerts>(),
  readAlert: vi.fn<typeof inventoryApi.readAlert>(),
}))
vi.mock('vue-router', async (importOriginal) => ({
  ...(await importOriginal<typeof import('vue-router')>()),
  useRouter: () => ({ push: vi.fn<() => Promise<void>>() }),
}))

const api = vi.mocked(inventoryApi)
const page = <T>(results: T[]) => ({ count: results.length, next: null, previous: null, results })

function signIn(id: number, roles: string[]) {
  useAuthStore().user = {
    id,
    is_admin: false,
    role_refs: roles.map((key) => ({ key, name: key, is_system: true })),
  } as unknown as User
}

const ASSET = {
  id: 1,
  horizon_id: 'H000000018',
  model: 'Dell Latitude 5440',
  serial: 'ABC1234',
  status: 'blocked',
  customer: 'TransRápido',
  lot: 'LOT-2026-0001',
  location: 'SP01-QUA',
} as inventoryApi.AssetSummary

const BLOCK = {
  id: 4,
  asset: 1,
  asset_detail: ASSET,
  report: 9,
  block_type: 'mdm',
  status: 'open',
  notified_at: null,
  due_date: null,
  days_left: null,
  finding_value: '500.00',
  decision: '',
  decision_notes: '',
  evidence: [],
} as unknown as inventoryApi.BlockFollowUp

describe('blocks', () => {
  beforeEach(() => {
    setLanguage('en')
    setActivePinia(createPinia())
  })
  afterEach(() => {
    vi.clearAllMocks()
    document.body.innerHTML = ''
  })

  it('commercial selects blocks and marks them notified', async () => {
    signIn(3, ['commercial_finance'])
    api.listBlocks.mockResolvedValue(page([BLOCK]))
    api.notifyBlocks.mockResolvedValue([])
    const wrapper = mountWithPlugins(BlocksView)
    await settle()
    expect(wrapper.find('[data-testid="block-row"]').text()).toContain('Not notified yet')
    await wrapper.find('[data-testid="block-row"] input[type="checkbox"]').setValue(true)
    await settle()
    await click('notify')
    expect(api.notifyBlocks).toHaveBeenCalledWith([4])
    wrapper.unmount()
  })

  it('shows the days left, or how long it is overdue', async () => {
    signIn(3, ['commercial_finance'])
    api.listBlocks.mockResolvedValue(
      page([
        {
          ...BLOCK,
          id: 5,
          notified_at: '2026-11-20T10:00:00Z',
          due_date: '2026-12-01',
          days_left: 3,
        },
        {
          ...BLOCK,
          id: 6,
          notified_at: '2026-11-01T10:00:00Z',
          due_date: '2026-11-16',
          days_left: -2,
        },
      ]),
    )
    const wrapper = mountWithPlugins(BlocksView)
    await settle()
    const rows = wrapper.findAll('[data-testid="block-row"]').map((r) => r.text())
    expect(rows[0]).toContain('3 days left')
    expect(rows[1]).toContain('2 days overdue')
    wrapper.unmount()
  })
})

describe('disputes', () => {
  beforeEach(() => {
    setLanguage('en')
    setActivePinia(createPinia())
    api.listCharges.mockResolvedValue(page([]))
  })
  afterEach(() => {
    vi.clearAllMocks()
    document.body.innerHTML = ''
  })

  const DISPUTE = {
    id: 2,
    report: 9,
    report_version: 1,
    report_technician: 5,
    asset_detail: ASSET,
    findings: [11, 12],
    findings_detail: [
      { id: 11, kind: 'damage', item: '', description: 'Dent', value: '200.00' },
      { id: 12, kind: 'customization', item: '', description: 'Sticker', value: '50.00' },
    ],
    justification: 'Both existed before',
    registered_by_name: 'Carla',
    registered_at: '2026-11-24T10:00:00Z',
    analysis_due: '2026-12-01',
    analyst: 7,
    analyst_name: 'Sam',
    status: 'in_analysis',
    decision: '',
    new_report: null,
  } as unknown as inventoryApi.Dispute

  it('a supervisor decides partly: the chosen findings are cancelled', async () => {
    signIn(7, ['inventory_supervisor'])
    api.listDisputes.mockResolvedValue(page([DISPUTE]))
    api.decideDispute.mockResolvedValue({
      ...DISPUTE,
      status: 'decided',
      decision: 'partially_upheld',
    })
    const wrapper = mountWithPlugins(DisputesView)
    await settle()
    await wrapper.find('[data-testid="disputes"] tbody tr').trigger('click')
    await settle()
    const radios = document.body.querySelectorAll<HTMLInputElement>(
      '.v-radio-group input[type="radio"]',
    )
    radios[1]!.click() // partially upheld
    await settle()
    const boxes = document.body.querySelectorAll<HTMLInputElement>(
      '.v-dialog .v-list input[type="checkbox"]',
    )
    boxes[1]!.click() // the sticker
    await settle()
    const notes = inBody('[data-testid="decision-notes"] textarea') as HTMLTextAreaElement
    notes.value = 'Sticker was ours'
    notes.dispatchEvent(new Event('input'))
    await settle()
    await click('decide-dispute')
    expect(api.decideDispute).toHaveBeenCalledWith(2, {
      decision: 'partially_upheld',
      notes: 'Sticker was ours',
      upheld_findings: [12],
      reinspected: false,
    })
    wrapper.unmount()
  })

  it("the report's technician does not analyse it", async () => {
    signIn(5, ['inventory_supervisor'])
    api.listDisputes.mockResolvedValue(page([{ ...DISPUTE, status: 'open', analyst: null }]))
    const wrapper = mountWithPlugins(DisputesView)
    await settle()
    await wrapper.find('[data-testid="disputes"] tbody tr').trigger('click')
    await settle()
    expect(inBody('[data-testid="analyze"]')).toBeNull()
    expect(document.body.textContent).toContain('another supervisor must analyse')
    wrapper.unmount()
  })
})

describe('alerts', () => {
  afterEach(() => {
    vi.clearAllMocks()
    document.body.innerHTML = ''
  })

  it('shows the unread count and the alerts translated', async () => {
    setLanguage('en')
    setActivePinia(createPinia())
    api.alertCount.mockResolvedValue({ unread: 2 })
    api.listAlerts.mockResolvedValue(
      page([
        {
          id: 1,
          kind: 'aging',
          severity: 'warning',
          scope: 'user',
          params: { asset: 'H1', status: 'blocked', days: 9 },
          ref: 'asset:1',
          created_at: '2026-11-24T10:00:00Z',
          read: false,
        },
      ]),
    )
    const wrapper = mountWithPlugins(AlertsMenu)
    await settle()
    expect(wrapper.find('.v-badge').text()).toContain('2')
    await click('notifications')
    expect(inBody('[data-testid="alert"]')!.textContent).toContain(
      'H1 has been Blocked for 9 days.',
    )
    wrapper.unmount()
  })
})
