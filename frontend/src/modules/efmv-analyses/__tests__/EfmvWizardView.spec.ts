import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createMemoryHistory, createRouter } from 'vue-router'

import { ApiError } from '@/api'
import { i18n, setLanguage } from '@/i18n'
import * as managersApi from '@/modules/account-managers/api'
import * as verticalsApi from '@/modules/catalogs/verticals/api'
import * as customersApi from '@/modules/customers/api'
import vuetify from '@/plugins/vuetify'
import { useAuthStore } from '@/stores/auth'
import { click, inBody, openDropdown, pickOption, settle } from '@/test-utils'
import * as efmvApi from '../api'
import EfmvWizardView from '../EfmvWizardView.vue'

vi.mock('../api', () => ({
  createEfmvAnalysis: vi.fn<typeof efmvApi.createEfmvAnalysis>(),
  getAccountManagerSummary: vi.fn<typeof efmvApi.getAccountManagerSummary>(),
}))
vi.mock('@/modules/customers/api', () => ({
  listCustomers: vi.fn<typeof customersApi.listCustomers>(),
}))
vi.mock('@/modules/account-managers/api', () => ({
  listAccountManagers: vi.fn<typeof managersApi.listAccountManagers>(),
}))
vi.mock('@/modules/catalogs/verticals/api', () => ({
  listSubVerticals: vi.fn<typeof verticalsApi.listSubVerticals>(),
}))

const efmv = vi.mocked(efmvApi)
const customers = vi.mocked(customersApi)
const managers = vi.mocked(managersApi)
const verticals = vi.mocked(verticalsApi)

const page = <T>(results: T[]) => ({ count: results.length, next: null, previous: null, results })

const SUMMARY: efmvApi.AccountManagerSummary = {
  id: 10,
  full_name: 'Ana Lima',
  email: 'ana@example.com',
  job_title: 'Account Manager',
  photo_version: 'p1',
  verticals: [{ id: 1, name: 'Industry' }],
  analyses_count: 7,
  top_verticals: [
    { id: 1, name: 'Industry', analyses: 5 },
    { id: 2, name: 'Healthcare', analyses: 2 },
  ],
  primary_customers_count: 4,
}

async function mountWizard(roles = ['Account Manager']) {
  const pinia = createPinia()
  setActivePinia(pinia)
  useAuthStore().user = {
    id: 10,
    username: 'ana',
    name: 'Ana Lima',
    is_admin: false,
    roles,
    photo_version: null,
    preferences: {
      language: 'en',
      theme: 'light',
      color_theme: 'metallic_foundations',
      ui_scale: 'auto',
      date_format: 'auto',
      time_format: 'auto',
      select_on_focus: true,
      auto_scope: true,
      scope_threshold: '5.00',
      updated_at: '',
    },
  }
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/', name: 'efmv-analyses-list', component: { render: () => null } },
      { path: '/new', name: 'efmv-analysis-new', component: { render: () => null } },
      { path: '/:id', name: 'efmv-analysis', component: { render: () => null } },
    ],
  })
  await router.push('/new')
  const replace = vi.spyOn(router, 'replace')
  const wrapper = mount(EfmvWizardView, {
    attachTo: document.body,
    global: { plugins: [vuetify, i18n, pinia, router] },
  })
  await settle()
  return { wrapper, replace }
}

const currentStep = () => inBody('.step.current')!.textContent!.trim()

describe('EfmvWizardView', () => {
  beforeEach(() => {
    setLanguage('en')
    customers.listCustomers.mockResolvedValue(
      page([{ id: 20, name: 'Acme Ltda', trade_name: '' } as customersApi.Customer]),
    )
    managers.listAccountManagers.mockResolvedValue(page([]))
    verticals.listSubVerticals.mockResolvedValue(
      page([
        {
          id: 10,
          name: 'General',
          is_general: true,
          label: 'Industry / General',
          vertical: { id: 1, name: 'Industry', is_enabled: true },
          allowed_terms: [36],
          recommended_term: 36,
        },
        {
          id: 11,
          name: 'Yellow line',
          is_general: false,
          label: 'Industry / Yellow line',
          vertical: { id: 1, name: 'Industry', is_enabled: true },
          allowed_terms: [36],
          recommended_term: 36,
        },
        {
          id: 20,
          name: 'General',
          is_general: true,
          label: 'Healthcare / General',
          vertical: { id: 2, name: 'Healthcare', is_enabled: true },
          allowed_terms: [36],
          recommended_term: 36,
        },
      ]),
    )
    efmv.getAccountManagerSummary.mockResolvedValue(SUMMARY)
  })
  afterEach(() => {
    vi.clearAllMocks()
    document.body.innerHTML = ''
  })

  it('goes through the three steps and creates the analysis with its premises', async () => {
    const { wrapper, replace } = await mountWizard()
    expect(currentStep()).toContain('Premises')
    // The account manager is the user, with their figures
    expect(efmv.getAccountManagerSummary).toHaveBeenCalledWith(10)
    const card = inBody('[data-testid="manager-card"]')!
    expect(inBody('[data-testid="manager-name"]')!.textContent).toContain('Ana Lima')
    expect(inBody('[data-testid="manager-analyses"]')!.textContent).toContain('7')
    expect(inBody('[data-testid="manager-customers"]')!.textContent).toContain('4')
    const tops = [...card.querySelectorAll('[data-testid="manager-top-vertical"]')]
    expect(tops.map((el) => el.textContent)).toEqual([
      expect.stringMatching(/Industry\s*5 analyses/),
      expect.stringMatching(/Healthcare\s*2 analyses/),
    ])
    expect(card.querySelector('img')!.getAttribute('src')).toBe('/api/users/10/photo/?v=p1')

    // Customer and vertical are required before going on
    await click('wizard-next')
    expect(currentStep()).toContain('Premises')
    await pickOption('customer', 'Acme Ltda')
    expect(customers.listCustomers).toHaveBeenCalledWith(
      expect.objectContaining({ filters: { account_manager: 10, is_active: true } }),
    )
    await pickOption('vertical', 'Yellow line')
    await click('wizard-next')
    expect(currentStep()).toContain('Services')
    expect(inBody('[data-testid="step-services-content"]')!.textContent).toContain('Coming Soon')
    await click('wizard-next')
    expect(currentStep()).toContain('Partnerships and Alliances')
    // Back to an earlier step and forward again
    await click('wizard-back')
    expect(currentStep()).toContain('Services')
    await click('wizard-next')

    efmv.createEfmvAnalysis.mockResolvedValue({ id: 4, code: 'EFMV-2026-0004' } as never)
    await click('wizard-create')
    expect(efmv.createEfmvAnalysis).toHaveBeenCalledWith({
      account_manager: 10,
      customer: 20,
      vertical: 1,
      sub_vertical: 11,
      // A first scenario, called by its term
      scenarios: [{ name: '', term_months: 36, scope: '', items: [] }],
    })
    expect(replace).toHaveBeenCalledWith({ name: 'efmv-analysis', params: { id: 4 } })
    wrapper.unmount()
  })

  it('only the verticals the account manager works in are offered', async () => {
    const { wrapper } = await mountWizard()
    await openDropdown('vertical')
    const offered = [...document.querySelectorAll('.v-overlay--active .v-list-item-title')].map(
      (el) => el.textContent!.trim(),
    )
    expect(offered).toContain('Industry')
    expect(offered).not.toContain('Healthcare')
    wrapper.unmount()
  })

  it('an account manager without verticals: none to choose, and why', async () => {
    efmv.getAccountManagerSummary.mockResolvedValue({ ...SUMMARY, verticals: [] })
    const { wrapper } = await mountWizard()
    expect(inBody('[data-testid="vertical"]')!.textContent).toContain('works in no vertical yet')
    await click('wizard-next')
    expect(currentStep()).toContain('Premises')
    wrapper.unmount()
  })

  it('without the Account Manager role the account manager is chosen first', async () => {
    const { wrapper } = await mountWizard(['Administrator'])
    expect(inBody('[data-testid="customer-disabled"]')).not.toBeNull()
    expect(inBody('[data-testid="manager-card"]')!.textContent).toContain(
      'Choose an account manager',
    )
    expect(efmv.getAccountManagerSummary).not.toHaveBeenCalled()
    await click('wizard-next')
    expect(currentStep()).toContain('Premises')
    wrapper.unmount()
  })

  it('what the server refuses brings the premises back', async () => {
    const { wrapper } = await mountWizard()
    await pickOption('customer', 'Acme Ltda')
    await pickOption('vertical', 'Industry')
    await click('wizard-next')
    await click('wizard-next')
    efmv.createEfmvAnalysis.mockRejectedValue(
      new ApiError(400, 'Bad Request', {
        customer: ['This account manager does not serve this customer.'],
      }),
    )
    await click('wizard-create')
    expect(currentStep()).toContain('Premises')
    expect(inBody('[data-testid="customer"]')!.textContent).toContain('does not serve')
    expect(inBody('[data-testid="form-error"]')).not.toBeNull()
    wrapper.unmount()
  })
})
