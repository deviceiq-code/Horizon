import { createPinia, setActivePinia } from 'pinia'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { ApiError } from '@/api'
import { setLanguage } from '@/i18n'
import { useNotificationsStore } from '@/stores/notifications'
import { inBody, mountWithPlugins, settle, typeInto } from '@/test-utils'
import * as managersApi from '../api'
import AccountManagersView from '../AccountManagersView.vue'

vi.mock('../api', () => ({
  listAccountManagers: vi.fn<typeof managersApi.listAccountManagers>(),
  createAccountManager: vi.fn<typeof managersApi.createAccountManager>(),
  updateAccountManager: vi.fn<typeof managersApi.updateAccountManager>(),
  deleteAccountManager: vi.fn<typeof managersApi.deleteAccountManager>(),
}))

const api = vi.mocked(managersApi)

const ANA = {
  id: 1,
  full_name: 'Ana Souza',
  email: 'ana@example.com',
  created_at: '',
  updated_at: '',
}
const BRUNO = { ...ANA, id: 2, full_name: 'Bruno Lima', email: 'bruno@corp.com' }

const mountView = () => mountWithPlugins(AccountManagersView)

describe('AccountManagersView', () => {
  beforeEach(() => {
    setLanguage('en')
    setActivePinia(createPinia())
    api.listAccountManagers.mockResolvedValue({
      count: 2,
      next: null,
      previous: null,
      results: [ANA, BRUNO],
    })
  })

  afterEach(() => {
    vi.clearAllMocks()
    document.body.innerHTML = ''
  })

  it('loads the first page sorted by name and shows the rows', async () => {
    const wrapper = mountView()
    await settle()

    expect(api.listAccountManagers).toHaveBeenCalledWith({
      page: 1,
      pageSize: 25,
      search: '',
      ordering: 'full_name',
    })
    const text = wrapper.text()
    expect(text).toContain('Ana Souza')
    expect(text).toContain('bruno@corp.com')
    expect(wrapper.findAll('tbody tr')).toHaveLength(2)
    wrapper.unmount()
  })

  it('searches on the server after the user stops typing', async () => {
    const wrapper = mountView()
    await settle()
    api.listAccountManagers.mockClear()

    await wrapper.find('[data-testid="search"] input').setValue('bruno')
    expect(api.listAccountManagers).not.toHaveBeenCalled() // debounced (300 ms)
    await new Promise((r) => setTimeout(r, 400))
    await settle()

    expect(api.listAccountManagers).toHaveBeenLastCalledWith(
      expect.objectContaining({ search: 'bruno', page: 1 }),
    )
    wrapper.unmount()
  })

  it('shows an error with a retry button when loading fails', async () => {
    api.listAccountManagers.mockRejectedValueOnce(new ApiError(500, 'boom'))
    const wrapper = mountView()
    await settle()
    expect(wrapper.text()).toContain('Could not load the data.')
    wrapper.unmount()
  })

  it('deletes after confirmation and reloads the grid', async () => {
    api.deleteAccountManager.mockResolvedValue(undefined)
    const wrapper = mountView()
    await settle()
    api.listAccountManagers.mockClear()

    await wrapper.findAll('[data-testid="delete"]')[0]!.trigger('click')
    await settle()
    expect(document.body.textContent).toContain('Delete "Ana Souza"?')
    expect(api.deleteAccountManager).not.toHaveBeenCalled()

    inBody('[data-testid="confirm-button"]')!.click()
    await settle()

    expect(api.deleteAccountManager).toHaveBeenCalledWith(1)
    expect(api.listAccountManagers).toHaveBeenCalledTimes(1)
    expect(useNotificationsStore().text).toBe('Account manager deleted.')
    wrapper.unmount()
  })

  it('shows the server reason when deletion is refused', async () => {
    api.deleteAccountManager.mockRejectedValue(
      new ApiError(409, 'This account manager has customers and cannot be deleted.'),
    )
    const wrapper = mountView()
    await settle()

    await wrapper.findAll('[data-testid="delete"]')[0]!.trigger('click')
    await settle()
    inBody('[data-testid="confirm-button"]')!.click()
    await settle()

    const notifications = useNotificationsStore()
    expect(notifications.text).toBe('This account manager has customers and cannot be deleted.')
    expect(notifications.color).toBe('error')
    wrapper.unmount()
  })

  it('creates a new account manager through the form', async () => {
    api.createAccountManager.mockResolvedValue({ ...ANA, id: 3, full_name: 'Carla' })
    const wrapper = mountView()
    await settle()

    await wrapper.find('[data-testid="new"]').trigger('click')
    await settle()
    await typeInto('full-name', '  Carla  ')
    await typeInto('email', 'carla@example.com')
    inBody('[data-testid="save"]')!.click()
    await settle()

    expect(api.createAccountManager).toHaveBeenCalledWith({
      full_name: 'Carla',
      email: 'carla@example.com',
    })
    expect(useNotificationsStore().text).toBe('Account manager created.')
    wrapper.unmount()
  })

  it('does not submit the form when fields are invalid', async () => {
    const wrapper = mountView()
    await settle()

    await wrapper.find('[data-testid="new"]').trigger('click')
    await settle()
    await typeInto('email', 'not-an-email')
    inBody('[data-testid="save"]')!.click()
    await settle()

    expect(api.createAccountManager).not.toHaveBeenCalled()
    expect(document.body.textContent).toContain('This field is required.')
    expect(document.body.textContent).toContain('Enter a valid email address.')
    wrapper.unmount()
  })

  it('shows the server validation error on the email field', async () => {
    api.updateAccountManager.mockRejectedValue(
      new ApiError(400, 'Bad Request', {
        email: ['An account manager with this email already exists.'],
      }),
    )
    const wrapper = mountView()
    await settle()

    await wrapper.findAll('[data-testid="edit"]')[0]!.trigger('click')
    await settle()
    const name = inBody('[data-testid="full-name"] input') as HTMLInputElement
    expect(name.value).toBe('Ana Souza')
    inBody('[data-testid="save"]')!.click()
    await settle()

    expect(api.updateAccountManager).toHaveBeenCalledWith(1, {
      full_name: 'Ana Souza',
      email: 'ana@example.com',
    })
    expect(document.body.textContent).toContain(
      'An account manager with this email already exists.',
    )
    wrapper.unmount()
  })
})
