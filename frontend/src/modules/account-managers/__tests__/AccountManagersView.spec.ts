import { createPinia, setActivePinia } from 'pinia'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { ApiError } from '@/api'
import { setLanguage } from '@/i18n'
import { useNotificationsStore } from '@/stores/notifications'
import * as verticalsApi from '@/modules/catalogs/verticals/api'
import { inBody, mountWithPlugins, settle, typeInto } from '@/test-utils'
import * as managersApi from '../api'
import AccountManagersView from '../AccountManagersView.vue'

vi.mock('../api', () => ({
  listAccountManagers: vi.fn<typeof managersApi.listAccountManagers>(),
  createAccountManager: vi.fn<typeof managersApi.createAccountManager>(),
  updateAccountManager: vi.fn<typeof managersApi.updateAccountManager>(),
  deleteAccountManager: vi.fn<typeof managersApi.deleteAccountManager>(),
  uploadAccountManagerPhoto: vi.fn<typeof managersApi.uploadAccountManagerPhoto>(),
  deleteAccountManagerPhoto: vi.fn<typeof managersApi.deleteAccountManagerPhoto>(),
  accountManagerPhotoUrl: (id: number, version: string) => `/photo/${id}?v=${version}`,
}))
// Canvas is not available here: the crop is checked in the browser
vi.mock('@/utils/image', () => ({
  squareImage: vi.fn<(file: File) => Promise<File>>(
    async (file) => new File([file], 'square.jpg', { type: 'image/jpeg' }),
  ),
}))
vi.mock('@/modules/catalogs/verticals/api', () => ({
  listVerticals: vi.fn<typeof verticalsApi.listVerticals>(),
}))

const api = vi.mocked(managersApi)
const verticals = vi.mocked(verticalsApi)

const vertical = (id: number, name: string, is_enabled = true) => ({ id, name, is_enabled })

const ANA: managersApi.AccountManager = {
  id: 1,
  first_name: 'Ana',
  last_name: 'Souza',
  full_name: 'Ana Souza',
  email: 'ana@example.com',
  verticals: [1, 2, 3, 4],
  verticals_detail: [
    vertical(1, 'Health'),
    vertical(2, 'Industry'),
    vertical(3, 'IT'),
    vertical(4, 'Mining', false),
  ],
  photo_version: null,
  created_at: '',
  updated_at: '',
}
const BRUNO: managersApi.AccountManager = {
  ...ANA,
  id: 2,
  full_name: 'Bruno Lima',
  email: 'bruno@corp.com',
  verticals: [],
  verticals_detail: [],
}

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
    verticals.listVerticals.mockResolvedValue({
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

  it('shows the verticals each account manager works in', async () => {
    const wrapper = mountView()
    await settle()

    const [ana, bruno] = wrapper.findAll('tbody tr').map((r) => r.text())
    expect(ana).toContain('Health')
    expect(ana).toContain('IT')
    expect(ana).not.toContain('Mining') // beyond the first 3 chips…
    expect(ana).toContain('+1') // …summarized
    expect(bruno).toContain('—')
    wrapper.unmount()
  })

  it('the form offers only enabled verticals and shows the selected ones', async () => {
    verticals.listVerticals.mockResolvedValue({
      count: 1,
      next: null,
      previous: null,
      results: [
        {
          ...vertical(5, 'Agribusiness'),
          account_managers_detail: [],
          notes: '',
          sub_verticals: [],
          created_at: '',
          updated_at: '',
        },
      ],
    })
    const wrapper = mountView()
    await settle()

    await wrapper.findAll('[data-testid="edit"]')[0]!.trigger('click')
    await settle()

    expect(verticals.listVerticals).toHaveBeenCalledWith(
      expect.objectContaining({ filters: { is_enabled: true } }),
    )
    const field = inBody('[data-testid="verticals"]')!.textContent
    expect(field).toContain('Health')
    expect(field).toContain('Mining (Disabled)') // already assigned, though disabled since
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
    await typeInto('first-name', '  Carla  ')
    await typeInto('last-name', ' Mendes ')
    await typeInto('email', 'carla@example.com')
    inBody('[data-testid="save"]')!.click()
    await settle()

    expect(api.createAccountManager).toHaveBeenCalledWith({
      first_name: 'Carla',
      last_name: 'Mendes',
      email: 'carla@example.com',
      verticals: [],
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
    const first = inBody('[data-testid="first-name"] input') as HTMLInputElement
    const last = inBody('[data-testid="last-name"] input') as HTMLInputElement
    expect([first.value, last.value]).toEqual(['Ana', 'Souza'])
    inBody('[data-testid="save"]')!.click()
    await settle()

    expect(api.updateAccountManager).toHaveBeenCalledWith(1, {
      first_name: 'Ana',
      last_name: 'Souza',
      email: 'ana@example.com',
      verticals: [1, 2, 3, 4], // kept as they were
    })
    expect(document.body.textContent).toContain(
      'An account manager with this email already exists.',
    )
    wrapper.unmount()
  })

  // --- Photo ---------------------------------------------------------------------------------

  it('shows the photo in a circle, or the initials', async () => {
    api.listAccountManagers.mockResolvedValue({
      count: 2,
      next: null,
      previous: null,
      results: [
        { ...ANA, photo_version: 'abc' },
        { ...ANA, id: 2, full_name: 'Bruno Lima' },
      ],
    })
    const wrapper = mountView()
    await settle()
    const avatars = wrapper.findAll('tbody [data-testid="avatar"]')
    expect(avatars[0]!.find('img').attributes('src')).toBe('/photo/1?v=abc')
    expect(avatars[0]!.classes()).toContain('v-avatar')
    expect(avatars[1]!.text()).toBe('BL')
    wrapper.unmount()
  })

  it('sends the photo chosen in the form after creating the account manager', async () => {
    // Not in jsdom: the preview of the chosen picture
    URL.createObjectURL = vi.fn<(obj: Blob) => string>(() => 'blob:preview')
    URL.revokeObjectURL = vi.fn<(url: string) => void>()
    const created = { ...ANA, id: 3, full_name: 'Carla' }
    api.createAccountManager.mockResolvedValue(created)
    api.uploadAccountManagerPhoto.mockResolvedValue({ ...created, photo_version: 'new' })
    const wrapper = mountView()
    await settle()

    await wrapper.find('[data-testid="new"]').trigger('click')
    await settle()
    await typeInto('first-name', 'Carla')
    await typeInto('email', 'carla@example.com')
    const input = inBody('[data-testid="photo-input"]') as HTMLInputElement
    const picture = new File(['jpeg'], 'carla.png', { type: 'image/png' })
    Object.defineProperty(input, 'files', { value: [picture], configurable: true })
    input.dispatchEvent(new Event('change'))
    await settle()
    expect(
      inBody('[data-testid="photo"] [data-testid="avatar-photo"] img')!.getAttribute('src'),
    ).toBe('blob:preview')

    inBody('[data-testid="save"]')!.click()
    await settle()
    expect(api.uploadAccountManagerPhoto).toHaveBeenCalledTimes(1)
    const [id, sent] = api.uploadAccountManagerPhoto.mock.calls[0]!
    expect(id).toBe(3)
    expect((sent as File).name).toBe('square.jpg')
    wrapper.unmount()
  })

  it('removes the photo when saving after "Remove photo"', async () => {
    const withPhoto = { ...ANA, photo_version: 'abc' }
    api.listAccountManagers.mockResolvedValue({
      count: 1,
      next: null,
      previous: null,
      results: [withPhoto],
    })
    api.updateAccountManager.mockResolvedValue(withPhoto)
    api.deleteAccountManagerPhoto.mockResolvedValue(undefined)
    const wrapper = mountView()
    await settle()

    await wrapper.find('[data-testid="edit"]').trigger('click')
    await settle()
    inBody('[data-testid="photo-remove"]')!.click()
    await settle()
    // Initials while the removal is pending
    expect(inBody('[data-testid="photo"] [data-testid="avatar-photo"]')).toBeNull()
    inBody('[data-testid="save"]')!.click()
    await settle()
    expect(api.deleteAccountManagerPhoto).toHaveBeenCalledWith(1)
    expect(api.uploadAccountManagerPhoto).not.toHaveBeenCalled()
    wrapper.unmount()
  })

  it('editing without touching the photo does not send it', async () => {
    api.updateAccountManager.mockResolvedValue(ANA)
    const wrapper = mountView()
    await settle()
    await wrapper.find('[data-testid="edit"]').trigger('click')
    await settle()
    inBody('[data-testid="save"]')!.click()
    await settle()
    expect(api.updateAccountManager).toHaveBeenCalled()
    expect(api.uploadAccountManagerPhoto).not.toHaveBeenCalled()
    expect(api.deleteAccountManagerPhoto).not.toHaveBeenCalled()
    wrapper.unmount()
  })
})
