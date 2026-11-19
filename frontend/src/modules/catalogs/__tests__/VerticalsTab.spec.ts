import { createPinia, setActivePinia } from 'pinia'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { ApiError } from '@/api'
import { setLanguage } from '@/i18n'
import * as managersApi from '@/modules/account-managers/api'
import { useNotificationsStore } from '@/stores/notifications'
import { click, inBody, mountWithPlugins, settle, typeInto } from '@/test-utils'
import * as verticalsApi from '../verticals/api'
import VerticalsTab from '../verticals/VerticalsTab.vue'

vi.mock('../verticals/api', async (importOriginal) => ({
  ...(await importOriginal<typeof import('../verticals/api')>()),
  listVerticals: vi.fn<typeof verticalsApi.listVerticals>(),
  getVerticalDefaults: vi.fn<typeof verticalsApi.getVerticalDefaults>(),
  createVertical: vi.fn<typeof verticalsApi.createVertical>(),
  updateVertical: vi.fn<typeof verticalsApi.updateVertical>(),
  deleteVertical: vi.fn<typeof verticalsApi.deleteVertical>(),
}))
vi.mock('@/modules/account-managers/api', () => ({
  listAccountManagers: vi.fn<typeof managersApi.listAccountManagers>(),
}))

const api = vi.mocked(verticalsApi)
const managers = vi.mocked(managersApi)

const manager = (id: number, full_name: string) => ({ id, full_name })

const DEFAULTS: verticalsApi.SubVerticalDefaults = {
  risk: 'medium',
  allowed_terms: [12, 24, 36, 48, 60],
  recommended_term: 36,
  max_term_months: 360,
}

const INDUSTRY: verticalsApi.Vertical = {
  id: 1,
  name: 'Industry',
  account_managers: [1, 2, 3, 4, 5],
  account_managers_detail: [
    manager(1, 'Ana Souza'),
    manager(2, 'Bruno Lima'),
    manager(3, 'Carla Mendes'),
    manager(4, 'Diego Alves'),
    manager(5, 'Elisa Rocha'),
  ],
  is_enabled: true,
  notes: 'Factories and plants.',
  sub_verticals: [
    {
      id: 10,
      name: '',
      is_general: true,
      risk: 'medium',
      allowed_terms: [12, 24, 36],
      recommended_term: 36,
    },
    {
      id: 11,
      name: 'Yellow line',
      is_general: false,
      risk: 'high',
      allowed_terms: [24, 36],
      recommended_term: 24,
    },
  ],
  created_at: '',
  updated_at: '',
}
const MINING: verticalsApi.Vertical = {
  ...INDUSTRY,
  id: 2,
  name: 'Mining',
  account_managers: [],
  account_managers_detail: [],
  is_enabled: false,
  notes: '',
  sub_verticals: [INDUSTRY.sub_verticals[0]!],
}

const mountTab = () => mountWithPlugins(VerticalsTab)

async function openNew(wrapper: ReturnType<typeof mountTab>) {
  await wrapper.find('[data-testid="new"]').trigger('click')
  await settle()
}

async function openEdit(wrapper: ReturnType<typeof mountTab>, row: number) {
  await wrapper.findAll('[data-testid="edit"]')[row]!.trigger('click')
  await settle()
}

describe('VerticalsTab', () => {
  beforeEach(() => {
    setLanguage('en')
    setActivePinia(createPinia())
    api.listVerticals.mockResolvedValue({
      count: 2,
      next: null,
      previous: null,
      results: [INDUSTRY, MINING],
    })
    api.getVerticalDefaults.mockResolvedValue(DEFAULTS)
    managers.listAccountManagers.mockResolvedValue({
      count: 0,
      next: null,
      previous: null,
      results: [],
    })
  })

  afterEach(() => {
    vi.clearAllMocks()
    document.body.innerHTML = ''
  })

  // --- Grid ----------------------------------------------------------------------------------

  it('lists verticals with sub-vertical count, account managers and status', async () => {
    const wrapper = mountTab()
    await settle()

    const [industry, mining] = wrapper.findAll('tbody tr').map((r) => r.text())
    expect(industry).toContain('Factories and plants.')
    expect(industry).toContain('2 sub-verticals')
    expect(industry).toContain('Ana Souza')
    expect(industry).not.toContain('Diego Alves') // beyond the first 3 chips…
    expect(industry).toContain('+2') // …summarized
    expect(industry).toContain('Enabled')
    expect(mining).toContain('1 sub-vertical')
    expect(mining).toContain('Disabled')
    wrapper.unmount()
  })

  it('expands a row to show its sub-verticals', async () => {
    const wrapper = mountTab()
    await settle()
    expect(wrapper.find('[data-testid="sub-verticals-table"]').exists()).toBe(false)

    await wrapper.findAll('tbody tr')[0]!.find('button').trigger('click') // expand toggle
    await settle()

    const rows = wrapper.findAll('[data-testid="sub-vertical-row"]').map((r) => r.text())
    expect(rows).toHaveLength(2)
    expect(rows[0]).toContain('General')
    expect(rows[0]).toContain('Medium')
    expect(rows[0]).toContain('12 · 24 · 36')
    expect(rows[0]).toContain('36 months')
    expect(rows[1]).toContain('Yellow line')
    expect(rows[1]).toContain('High')
    expect(rows[1]).toContain('24 months')
    wrapper.unmount()
  })

  // --- Create --------------------------------------------------------------------------------

  it('creates a vertical whose General sub-vertical starts with the backend defaults', async () => {
    api.createVertical.mockResolvedValue({ ...MINING, id: 3, name: 'IT' })
    const wrapper = mountTab()
    await settle()

    await openNew(wrapper)
    expect(api.getVerticalDefaults).toHaveBeenCalled()
    expect(inBody('[data-testid="sub-vertical-0"]')!.textContent).toContain('36 months')
    await typeInto('name', ' IT ')
    await click('save')

    expect(api.createVertical).toHaveBeenCalledWith({
      name: 'IT',
      account_managers: [],
      is_enabled: true,
      notes: '',
      sub_verticals: [
        {
          name: '',
          is_general: true,
          risk: 'medium',
          allowed_terms: [12, 24, 36, 48, 60],
          recommended_term: 36,
        },
      ],
    })
    expect(useNotificationsStore().text).toBe('Vertical created.')
    wrapper.unmount()
  })

  it('a new sub-vertical starts with the values of General', async () => {
    api.createVertical.mockResolvedValue({ ...MINING, id: 3, name: 'IT' })
    const wrapper = mountTab()
    await settle()

    await openNew(wrapper)
    await typeInto('name', 'IT')
    await click('add-sub-vertical')
    const newRow = inBody('[data-testid="sub-vertical-1"]')!
    const nameInput = newRow.querySelector<HTMLInputElement>('[data-testid="sub-name"] input')!
    nameInput.value = 'Datacenter'
    nameInput.dispatchEvent(new Event('input'))
    await settle()
    await click('save')

    const payload = api.createVertical.mock.calls[0]![0]
    expect(payload.sub_verticals[1]).toEqual({
      name: 'Datacenter',
      is_general: false,
      risk: 'medium',
      allowed_terms: [12, 24, 36, 48, 60],
      recommended_term: 36,
    })
    wrapper.unmount()
  })

  it('requires a name for each new sub-vertical', async () => {
    const wrapper = mountTab()
    await settle()

    await openNew(wrapper)
    await typeInto('name', 'IT')
    await click('add-sub-vertical')
    await click('save')

    expect(api.createVertical).not.toHaveBeenCalled()
    expect(inBody('[data-testid="sub-vertical-1"]')!.textContent).toContain(
      'This field is required.',
    )
    wrapper.unmount()
  })

  it('the General sub-vertical cannot be renamed or removed', async () => {
    const wrapper = mountTab()
    await settle()

    await openNew(wrapper)
    const general = inBody('[data-testid="sub-vertical-0"]')!
    expect(general.querySelector<HTMLInputElement>('input')!.value).toBe('General')
    expect(general.querySelector<HTMLInputElement>('input')!.readOnly).toBe(true)
    expect(general.querySelector('[data-testid="sub-remove"]')).toBeNull()
    wrapper.unmount()
  })

  // --- Edit ----------------------------------------------------------------------------------

  it('edits a vertical sending all its sub-verticals with their ids', async () => {
    api.updateVertical.mockResolvedValue(INDUSTRY)
    const wrapper = mountTab()
    await settle()

    await openEdit(wrapper, 0)
    const dialog = inBody('.v-dialog')!.textContent
    expect(dialog).toContain('Ana Souza') // selected managers show as chips
    expect(dialog).toContain('Elisa Rocha')
    await typeInto('name', 'Industry & Manufacturing')
    await click('save')

    expect(api.updateVertical).toHaveBeenCalledWith(1, {
      name: 'Industry & Manufacturing',
      account_managers: [1, 2, 3, 4, 5],
      is_enabled: true,
      notes: 'Factories and plants.',
      sub_verticals: INDUSTRY.sub_verticals,
    })
    expect(useNotificationsStore().text).toBe('Vertical updated.')
    wrapper.unmount()
  })

  it('removing a sub-vertical leaves it out of the saved list', async () => {
    api.updateVertical.mockResolvedValue(INDUSTRY)
    const wrapper = mountTab()
    await settle()

    await openEdit(wrapper, 0)
    inBody('[data-testid="sub-vertical-1"] [data-testid="sub-remove"]')!.click()
    await settle()
    await click('save')

    const payload = api.updateVertical.mock.calls[0]![1]
    expect(payload.sub_verticals.map((s) => s.id)).toEqual([10])
    wrapper.unmount()
  })

  // --- Server errors -------------------------------------------------------------------------

  it('shows server errors on the sub-vertical row that failed', async () => {
    api.updateVertical.mockRejectedValue(
      new ApiError(400, 'Bad Request', {
        sub_verticals: {
          '1': { recommended_term: ['The recommended term must be one of the allowed terms.'] },
        },
      }),
    )
    const wrapper = mountTab()
    await settle()

    await openEdit(wrapper, 0)
    await click('save')

    expect(inBody('[data-testid="sub-vertical-1"]')!.textContent).toContain(
      'The recommended term must be one of the allowed terms.',
    )
    expect(inBody('[data-testid="sub-vertical-0"]')!.textContent).not.toContain(
      'recommended term must',
    )
    wrapper.unmount()
  })

  it('shows server errors about the sub-vertical list as a whole', async () => {
    api.updateVertical.mockRejectedValue(
      new ApiError(400, 'Bad Request', {
        sub_verticals: ['Sub-vertical names must be unique within the vertical.'],
      }),
    )
    const wrapper = mountTab()
    await settle()

    await openEdit(wrapper, 0)
    await click('save')

    expect(document.body.textContent).toContain(
      'Sub-vertical names must be unique within the vertical.',
    )
    wrapper.unmount()
  })

  it('shows the server validation error on the name field', async () => {
    api.createVertical.mockRejectedValue(
      new ApiError(400, 'Bad Request', { name: ['A vertical with this name already exists.'] }),
    )
    const wrapper = mountTab()
    await settle()

    await openNew(wrapper)
    await typeInto('name', 'industry')
    await click('save')

    expect(document.body.textContent).toContain('A vertical with this name already exists.')
    wrapper.unmount()
  })

  // --- Delete --------------------------------------------------------------------------------

  it('deletes after confirmation', async () => {
    api.deleteVertical.mockResolvedValue(undefined)
    const wrapper = mountTab()
    await settle()

    await wrapper.findAll('[data-testid="delete"]')[1]!.trigger('click')
    await settle()
    expect(document.body.textContent).toContain('Delete "Mining"?')
    await click('confirm-button')

    expect(api.deleteVertical).toHaveBeenCalledWith(2)
    expect(useNotificationsStore().text).toBe('Vertical deleted.')
    wrapper.unmount()
  })
})
