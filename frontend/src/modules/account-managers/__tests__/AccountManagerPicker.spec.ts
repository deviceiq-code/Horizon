import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { defineComponent, h, ref } from 'vue'

import { setLanguage } from '@/i18n'
import { mountWithPlugins, settle } from '@/test-utils'
import * as managersApi from '../api'
import AccountManagerPicker from '../AccountManagerPicker.vue'

vi.mock('../api', () => ({
  listAccountManagers: vi.fn<typeof managersApi.listAccountManagers>(),
}))

const api = vi.mocked(managersApi)

const page = (results: { id: number; full_name: string }[]) => ({
  count: results.length,
  next: null,
  previous: null,
  results: results.map((r) => ({
    ...r,
    email: '',
    verticals: [],
    verticals_detail: [],
    created_at: '',
    updated_at: '',
  })),
})

/** Host component so v-model works as in a real form. */
function mountPicker(initial: number[], initialOptions: { id: number; full_name: string }[]) {
  const selected = ref<number[]>(initial)
  const Host = defineComponent(
    () => () =>
      h(AccountManagerPicker, {
        modelValue: selected.value,
        'onUpdate:modelValue': (v: number | number[] | null) => (selected.value = v as number[]),
        label: 'Account managers',
        multiple: true,
        initialOptions,
      }),
  )
  return { wrapper: mountWithPlugins(Host), selected }
}

describe('AccountManagerPicker', () => {
  beforeEach(() => setLanguage('en'))
  afterEach(() => {
    vi.clearAllMocks()
    document.body.innerHTML = ''
  })

  it('loads the first options from the server when mounted', async () => {
    api.listAccountManagers.mockResolvedValue(page([{ id: 1, full_name: 'Ana Souza' }]))
    const { wrapper } = mountPicker([], [])
    await settle()

    expect(api.listAccountManagers).toHaveBeenCalledWith({
      page: 1,
      pageSize: 20,
      search: '',
      ordering: 'full_name',
    })
    wrapper.unmount()
  })

  it('keeps showing selected managers that the server did not return', async () => {
    // The server's first page does not include Zoe, who is already selected
    api.listAccountManagers.mockResolvedValue(page([{ id: 1, full_name: 'Ana Souza' }]))
    const { wrapper } = mountPicker([9], [{ id: 9, full_name: 'Zoe Prado' }])
    await settle()

    expect(wrapper.text()).toContain('Zoe Prado')
    wrapper.unmount()
  })

  it('searches the server after the user stops typing', async () => {
    api.listAccountManagers.mockResolvedValue(page([]))
    const { wrapper } = mountPicker([], [])
    await settle()
    api.listAccountManagers.mockClear()

    await wrapper.find('input').setValue('bru')
    expect(api.listAccountManagers).not.toHaveBeenCalled()
    await new Promise((r) => setTimeout(r, 400))
    await settle()

    expect(api.listAccountManagers).toHaveBeenLastCalledWith(
      expect.objectContaining({ search: 'bru' }),
    )
    wrapper.unmount()
  })
})
