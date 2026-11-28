import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createMemoryHistory, createRouter } from 'vue-router'

import { ApiError } from '@/api'
import * as environment from '@/environment'
import { i18n, setLanguage } from '@/i18n'
import vuetify from '@/plugins/vuetify'
import { useAuthStore } from '@/stores/auth'
import { useNotificationsStore } from '@/stores/notifications'
import { click, inBody, pickOption, settle, typeInto, typeKeywords } from '@/test-utils'
import * as usersApi from '../api'
import type { Component } from 'vue'
import RolesView from '../RolesView.vue'
import UsersView from '../UsersView.vue'

vi.mock('../api', () => ({
  listUsers: vi.fn<typeof usersApi.listUsers>(),
  ID_DOCUMENT_TYPES: ['cpf', 'rg', 'national_id', 'passport', 'other'],
  ACCOUNT_MANAGER_ROLE: 'account_manager',
  createUser: vi.fn<typeof usersApi.createUser>(),
  updateUser: vi.fn<typeof usersApi.updateUser>(),
  deleteUser: vi.fn<typeof usersApi.deleteUser>(),
  listRoles: vi.fn<typeof usersApi.listRoles>(),
  allRoles: vi.fn<typeof usersApi.allRoles>(),
  createRole: vi.fn<typeof usersApi.createRole>(),
  updateRole: vi.fn<typeof usersApi.updateRole>(),
  deleteRole: vi.fn<typeof usersApi.deleteRole>(),
  uploadUserPhoto: vi.fn<typeof usersApi.uploadUserPhoto>(),
  deleteUserPhoto: vi.fn<typeof usersApi.deleteUserPhoto>(),
  userPhotoUrl: (id: number, version: string) => `/photo/${id}?v=${version}`,
}))
// Canvas is not available here: the crop is checked in the browser
vi.mock('@/utils/image', () => ({
  squareImage: vi.fn<(file: File) => Promise<File>>(
    async (file) => new File([file], 'square.jpg', { type: 'image/jpeg' }),
  ),
}))
const api = vi.mocked(usersApi)

const page = <T>(results: T[]) => ({ count: results.length, next: null, previous: null, results })

const ADMIN_ROLE: usersApi.Role = {
  id: 1,
  keywords: [],
  key: 'administrator',
  name: 'Administrator',
  description: 'Full access to the system.',
  is_system: true,
  users_count: 1,
  members: [{ id: 10, full_name: 'Fernando Almeida', photo_version: 'p1', is_active: true }],
  created_at: '',
}
const ANALYST: usersApi.Role = {
  ...ADMIN_ROLE,
  id: 2,
  key: '',
  name: 'Analyst',
  description: 'Prices',
  is_system: false,
  users_count: 0,
  members: [],
}

const FERNANDO: usersApi.User = {
  id: 10,
  keywords: [],
  environments: ['live'],
  username: 'fernando',
  first_name: 'Fernando',
  last_name: 'Almeida',
  full_name: 'Fernando Almeida',
  email: 'fernando@example.com',
  is_active: true,
  roles: [1],
  roles_detail: [{ id: 1, key: 'administrator', name: 'Administrator', is_system: true }],
  photo_version: null,
  has_password: true,
  id_document_type: '',
  id_document_number: '',
  employee_number: '',
  nationality: '',
  birth_date: null,
  job_title: '',
  department: '',
  work_location: '',
  manager: null,
  manager_name: null,
  hire_date: null,
  phone: '',
  mobile_phone: '',
  verticals: [],
  verticals_detail: [],
  last_login: '2026-11-19T15:00:00Z',
  date_joined: '',
}
const BRUNO: usersApi.User = {
  ...FERNANDO,
  id: 11,
  username: 'bruno',
  first_name: 'Bruno',
  last_name: 'Lima',
  full_name: 'Bruno Lima',
  is_active: false,
  roles: [2],
  roles_detail: [{ id: 2, key: '', name: 'Analyst', is_system: false }],
  last_login: null,
}

const AM_ROLE: usersApi.Role = {
  ...ADMIN_ROLE,
  id: 3,
  key: 'account_manager',
  name: 'Account Manager',
  description: 'Can be the account manager of customers.',
  users_count: 0,
}

async function mountView(path = '/users', view: Component = UsersView) {
  const pinia = createPinia()
  setActivePinia(pinia)
  useAuthStore().user = {
    id: 10,
    username: 'fernando',
    name: 'Fernando Almeida',
    is_admin: true,
    roles: ['Administrator'],
    photo_version: null,
    preferences: {
      language: 'en',
      theme: 'system',
      color_theme: 'metallic_foundations',
      ui_scale: 'auto',
      date_format: 'auto',
      time_format: 'auto',
      select_on_focus: true,
      word_dictionary: true,
      trim_spaces: true,
      journal_days: 7,
      auto_scope: true,
      scope_threshold: '5.00',
      number_format: 'auto',
      percent_places: 2,
      currency: 'BRL',
      currency_display: 'symbol',
      ui_state: {},
      user_name_display: 'full_name',
      full_name_order: 'first_last',
      searxng_url: '',
      web_search: true,
      web_search_engine: 'google',
      updated_at: '',
    },
  }
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/users', name: 'users', component: UsersView },
      { path: '/roles', name: 'roles', component: RolesView },
    ],
  })
  await router.push(path)
  const wrapper = mount(view, {
    attachTo: document.body,
    global: { plugins: [vuetify, i18n, pinia, router] },
  })
  await settle()
  return { wrapper, router }
}

const rowsText = () =>
  [...document.body.querySelectorAll('tbody tr')].map((r) => r.textContent ?? '')

describe('UsersView', () => {
  beforeEach(() => {
    setLanguage('en')
    api.listUsers.mockResolvedValue(page([BRUNO, FERNANDO]))
    api.listRoles.mockResolvedValue(page([ADMIN_ROLE, ANALYST]))
    api.allRoles.mockResolvedValue([ADMIN_ROLE, ANALYST])
  })

  afterEach(() => {
    vi.clearAllMocks()
    document.body.innerHTML = ''
  })

  // --- Users ---------------------------------------------------------------------------------

  it('lists users with roles, status and last sign-in; you cannot delete yourself', async () => {
    const { wrapper } = await mountView()
    const [bruno, fernando] = rowsText()
    expect(bruno).toContain('Bruno Lima')
    expect(bruno).toContain('Analyst')
    expect(bruno).toContain('Inactive')
    expect(bruno).toContain('Never')
    expect(fernando).toContain('You')
    expect(fernando).toContain('Administrator')
    expect(fernando).toContain('Active')
    const rows = document.body.querySelectorAll('tbody tr')
    expect(rows[0]!.querySelector('[data-testid="delete"]')).not.toBeNull()
    expect(rows[1]!.querySelector('[data-testid="delete"]')).toBeNull()
    wrapper.unmount()
  })

  it('shows system roles in the UI language', async () => {
    setLanguage('pt-br')
    const { wrapper } = await mountView()
    expect(rowsText()[1]).toContain('Administrador')
    wrapper.unmount()
  })

  it('creates a user with roles and a password', async () => {
    api.createUser.mockResolvedValue({ ...BRUNO, id: 12, username: 'carla' })
    const { wrapper } = await mountView()
    await click('new')
    await typeInto('username', ' carla ')
    await typeInto('first-name', 'Carla')
    await typeInto('email', 'carla@example.com')
    // Roles: pick "Analyst"
    inBody('[data-testid="roles"] .v-field')!.dispatchEvent(
      new MouseEvent('mousedown', { bubbles: true }),
    )
    await settle()
    const option = [
      ...document.body.querySelectorAll<HTMLElement>('.v-overlay--active .v-list-item'),
    ].find((el) => el.textContent?.trim() === 'Analyst')!
    option.click()
    await settle()
    await typeInto('password', 'Horizon-pass-2026')
    await typeInto('password-confirm', 'Horizon-pass-2026')
    await click('save')

    expect(api.createUser).toHaveBeenCalledWith(
      expect.objectContaining({
        username: 'carla',
        first_name: 'Carla',
        last_name: '',
        email: 'carla@example.com',
        is_active: true,
        roles: [2],
        password: 'Horizon-pass-2026',
        employee_number: '',
        birth_date: null,
        verticals: [],
      }),
    )
    expect(useNotificationsStore().text).toBe('User created.')
    wrapper.unmount()
  })

  it('requires matching passwords and a password for new users', async () => {
    const { wrapper } = await mountView()
    await click('new')
    await typeInto('username', 'carla')
    await click('save')
    expect(api.createUser).not.toHaveBeenCalled()
    expect(inBody('[data-testid="password"]')!.textContent).toContain('This field is required.')

    await typeInto('password', 'Horizon-pass-2026')
    await typeInto('password-confirm', 'other')
    await click('save')
    expect(api.createUser).not.toHaveBeenCalled()
    expect(inBody('[data-testid="password-confirm"]')!.textContent).toContain(
      'The passwords do not match.',
    )
    wrapper.unmount()
  })

  it('editing keeps the password when left empty; shows server refusals', async () => {
    api.updateUser.mockRejectedValue(
      new ApiError(409, 'You cannot remove the Administrator role from yourself.'),
    )
    const { wrapper } = await mountView()
    // Edit yourself: "active" cannot be switched off here
    document.body
      .querySelectorAll<HTMLElement>('tbody tr')[1]!
      .querySelector<HTMLElement>('[data-testid="edit"]')!
      .click()
    await settle()
    expect((inBody('[data-testid="is-active"] input') as HTMLInputElement).disabled).toBe(true)
    await click('save')
    const sent = api.updateUser.mock.calls[0]!
    expect(sent[0]).toBe(10)
    expect(sent[1]).not.toHaveProperty('password')
    expect(inBody('[data-testid="general-error"]')!.textContent).toContain(
      'You cannot remove the Administrator role from yourself.',
    )
    wrapper.unmount()
  })

  it('gives each user their environments in a selector as Roles: at least one', async () => {
    vi.spyOn(environment, 'fetchEnvironments').mockResolvedValue({
      environments: ['live', 'development'],
      current: 'live',
    })
    api.updateUser.mockResolvedValue(FERNANDO)
    const { wrapper } = await mountView()
    // Another user (not oneself)
    document.body
      .querySelectorAll<HTMLElement>('tbody tr')[0]!
      .querySelector<HTMLElement>('[data-testid="edit"]')!
      .click()
    await settle()
    expect(inBody('[data-testid="environments"]')!.textContent).toContain('Live')
    await pickOption('environments', 'Development (Test)')
    await click('save')
    expect(api.updateUser.mock.calls[0]![1]).toMatchObject({
      environments: ['live', 'development'],
    })
    wrapper.unmount()
  })

  it('a user without any environment cannot be saved', async () => {
    vi.spyOn(environment, 'fetchEnvironments').mockResolvedValue({
      environments: ['live', 'development'],
      current: 'live',
    })
    const { wrapper } = await mountView()
    document.body
      .querySelectorAll<HTMLElement>('tbody tr')[0]!
      .querySelector<HTMLElement>('[data-testid="edit"]')!
      .click()
    await settle()
    // Live off: nothing left
    await pickOption('environments', 'Live')
    await click('save')
    expect(api.updateUser).not.toHaveBeenCalled()
    expect(inBody('[data-testid="environments"]')!.textContent).toContain(
      'Choose at least one environment.',
    )
    wrapper.unmount()
  })

  // --- Roles ---------------------------------------------------------------------------------

  it('roles as cards: users and who they are; system roles cannot be edited or deleted', async () => {
    const many = Array.from({ length: 8 }, (_, i) => ({
      id: 20 + i,
      full_name: `User ${i + 1}`,
      photo_version: null,
      is_active: true,
    }))
    api.allRoles.mockResolvedValue([{ ...ANALYST, users_count: 8, members: many }, ADMIN_ROLE])
    const { wrapper } = await mountView('/roles', RolesView)
    expect(inBody('h1')!.textContent).toBe('Roles')
    const cards = document.body.querySelectorAll('[data-testid="role-card"]')
    // System roles first
    expect(cards[0]!.textContent).toContain('Administrator')
    expect(cards[0]!.textContent).toContain('System')
    expect(cards[0]!.textContent).toContain('Full access to the system.')
    expect(cards[0]!.querySelector('[data-testid="role-users-count"]')!.textContent).toContain(
      '1 user',
    )
    expect(cards[0]!.querySelector('[data-testid="role-member"]')!.textContent).toContain(
      'Fernando Almeida',
    )
    expect(cards[0]!.querySelector('[data-testid="edit"]')).toBeNull()
    expect(cards[0]!.querySelector('[data-testid="delete"]')).toBeNull()
    // Six members shown, then "+2 more"
    expect(cards[1]!.querySelectorAll('[data-testid="role-member"]')).toHaveLength(6)
    expect(cards[1]!.querySelector('[data-testid="role-more-members"]')!.textContent).toContain(
      '+2 more',
    )
    expect(cards[1]!.querySelector('[data-testid="edit"]')).not.toBeNull()
    wrapper.unmount()
  })

  it('deletes a role after confirmation; the reason when refused', async () => {
    api.allRoles.mockResolvedValue([ADMIN_ROLE, ANALYST])
    api.deleteRole.mockRejectedValue(
      new ApiError(409, 'This role has users and cannot be deleted.', {
        detail: 'This role has users and cannot be deleted.',
      }),
    )
    const { wrapper } = await mountView('/roles', RolesView)
    await click('delete')
    await click('confirm-button')
    expect(api.deleteRole).toHaveBeenCalledWith(2)
    expect(useNotificationsStore().text).toBe('This role has users and cannot be deleted.')
    wrapper.unmount()
  })

  it('creates a role', async () => {
    api.createRole.mockResolvedValue({ ...ANALYST, id: 3, name: 'Pricing' })
    const { wrapper } = await mountView('/roles', RolesView)
    await click('new')
    await typeInto('role-name', 'Pricing')
    await typeInto('role-description', 'Edits prices')
    await typeKeywords('Preços')
    await click('save')
    expect(api.createRole).toHaveBeenCalledWith({
      name: 'Pricing',
      description: 'Edits prices',
      keywords: ['preços'],
    })
    expect(useNotificationsStore().text).toBe('Role created.')
    wrapper.unmount()
  })

  // --- Photos --------------------------------------------------------------------------------

  it('shows photos in the grid and sends a new one after saving', async () => {
    URL.createObjectURL = vi.fn<(obj: Blob) => string>(() => 'blob:preview')
    URL.revokeObjectURL = vi.fn<(url: string) => void>()
    api.listUsers.mockResolvedValue(page([{ ...BRUNO, photo_version: 'abc' }, FERNANDO]))
    api.updateUser.mockResolvedValue(FERNANDO)
    api.uploadUserPhoto.mockResolvedValue({ ...FERNANDO, photo_version: 'new' })
    const { wrapper } = await mountView()
    const refresh = vi.spyOn(useAuthStore(), 'refresh').mockResolvedValue()

    const avatars = document.body.querySelectorAll('tbody [data-testid="avatar"]')
    expect(avatars[0]!.querySelector('img')!.getAttribute('src')).toBe('/photo/11?v=abc')
    expect(avatars[1]!.textContent?.trim()).toBe('FA') // initials without a photo

    // Your own user: a new photo, then the top bar is refreshed
    document.body
      .querySelectorAll<HTMLElement>('tbody tr')[1]!
      .querySelector<HTMLElement>('[data-testid="edit"]')!
      .click()
    await settle()
    const input = inBody('[data-testid="photo-input"]') as HTMLInputElement
    Object.defineProperty(input, 'files', {
      value: [new File(['x'], 'me.png', { type: 'image/png' })],
      configurable: true,
    })
    input.dispatchEvent(new Event('change'))
    await settle()
    await click('save')

    expect(api.uploadUserPhoto).toHaveBeenCalledTimes(1)
    expect(api.uploadUserPhoto.mock.calls[0]![0]).toBe(10)
    expect((api.uploadUserPhoto.mock.calls[0]![1] as File).name).toBe('square.jpg')
    expect(refresh).toHaveBeenCalled()
    wrapper.unmount()
  })

  // --- Employee data and account managers ----------------------------------------------------

  it('the form has Account, Personal Data and Employment tabs; Account Manager with the role', async () => {
    api.allRoles.mockResolvedValue([ADMIN_ROLE, ANALYST, AM_ROLE])
    api.createUser.mockResolvedValue({ ...BRUNO, id: 12 })
    const { wrapper } = await mountView()
    await click('new')
    expect(inBody('[data-testid="tab-personal"]')!.textContent).toContain('Personal Data')
    expect(inBody('[data-testid="tab-employment"]')!.textContent).toContain('Employment')
    expect(inBody('[data-testid="tab-account-manager"]')).toBeNull()

    await typeInto('username', 'carla')
    await typeInto('password', 'Horizon-pass-2026')
    await typeInto('password-confirm', 'Horizon-pass-2026')
    // The Account Manager role brings its tab
    inBody('[data-testid="roles"] .v-field')!.dispatchEvent(
      new MouseEvent('mousedown', { bubbles: true }),
    )
    await settle()
    ;[...document.body.querySelectorAll<HTMLElement>('.v-overlay--active .v-list-item')]
      .find((el) => el.textContent?.trim() === 'Account Manager')!
      .click()
    await settle()
    expect(inBody('[data-testid="tab-account-manager"]')).not.toBeNull()

    await click('tab-personal')
    await typeInto('id-document-number', '529.982.247-25')
    await click('tab-employment')
    await typeInto('employee-number', 'E-1042')
    await typeInto('job-title', 'Account Manager')
    await click('save')

    expect(api.createUser).toHaveBeenCalledWith(
      expect.objectContaining({
        username: 'carla',
        roles: [3],
        id_document_number: '529.982.247-25',
        employee_number: 'E-1042',
        job_title: 'Account Manager',
      }),
    )
    wrapper.unmount()
  })

  it('shows the server error on its field and opens its tab', async () => {
    api.createUser.mockRejectedValue(
      new ApiError(400, 'Bad Request', { id_document_number: ['Invalid CPF.'] }),
    )
    const { wrapper } = await mountView()
    await click('new')
    await typeInto('username', 'carla')
    await typeInto('password', 'Horizon-pass-2026')
    await typeInto('password-confirm', 'Horizon-pass-2026')
    await click('save')
    // The Personal Data tab is shown with the message
    expect(inBody('[data-testid="tab-personal"]')!.className).toContain('v-tab--selected')
    expect(inBody('[data-testid="id-document-number"]')!.textContent).toContain('Invalid CPF.')
    wrapper.unmount()
  })

  it('filters by role (opened with ?role=account_manager) and flags users without a password', async () => {
    api.allRoles.mockResolvedValue([ADMIN_ROLE, ANALYST, AM_ROLE])
    api.listUsers.mockResolvedValue(page([{ ...BRUNO, has_password: false, job_title: 'Analyst' }]))
    const { wrapper } = await mountView('/users?role=account_manager')
    expect(api.listUsers.mock.lastCall![0].filters).toEqual({ role: 'account_manager' })
    expect(inBody('[data-testid="filter-row"]')).not.toBeNull()
    const row = document.body.querySelector('tbody tr')!.textContent!
    expect(row).toContain('No Password')
    expect(row).toContain('Analyst')
    wrapper.unmount()
  })
})
