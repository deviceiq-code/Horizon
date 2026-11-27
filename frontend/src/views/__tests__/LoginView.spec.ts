import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { h } from 'vue'
import { createMemoryHistory, createRouter } from 'vue-router'
import { VApp } from 'vuetify/components'

import { ApiError } from '@/api'
import * as environment from '@/environment'
import { i18n, setLanguage } from '@/i18n'
import vuetify from '@/plugins/vuetify'
import { useAuthStore } from '@/stores/auth'
import { click, inBody, settle } from '@/test-utils'
import LoginView from '../LoginView.vue'

const Blank = { render: () => null }

async function mountLogin(environments: string[], current = 'live') {
  const pinia = createPinia()
  setActivePinia(pinia)
  vi.spyOn(environment, 'fetchEnvironments').mockResolvedValue({ environments, current })
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/', name: 'home', component: Blank },
      { path: '/login', name: 'login', component: LoginView },
    ],
  })
  await router.push('/login')
  // v-main needs the app's layout
  const wrapper = mount(
    { render: () => h(VApp, () => h(LoginView)) },
    {
      attachTo: document.body,
      global: { plugins: [vuetify, i18n, pinia, router] },
    },
  )
  await settle()
  return { wrapper, router }
}

describe('LoginView', () => {
  beforeEach(() => setLanguage('en'))
  afterEach(() => {
    vi.restoreAllMocks()
    document.body.innerHTML = ''
    document.cookie = `${environment.COOKIE_NAME}=; Path=/; Max-Age=0`
  })

  it('only Live on the server: no environment to choose', async () => {
    const { wrapper } = await mountLogin(['live'])
    // The logo: the mark, the name and the slogan
    const logo = inBody('[data-testid="horizon-logo"]')!
    expect(logo.querySelector('svg.horizon-mark')).not.toBeNull()
    expect(logo.textContent).toContain('Horizon')
    expect(logo.textContent).toContain('One Step Ahead')
    expect(inBody('[data-testid="environment"]')).toBeNull()
    wrapper.unmount()
  })

  it('chooses Development (Test) before signing in: kept in the cookie', async () => {
    const { wrapper, router } = await mountLogin(['live', 'development'])
    const toggle = inBody('[data-testid="environment"]')!
    expect(toggle.textContent).toContain('Live')
    expect(toggle.textContent).toContain('Development (Test)')
    expect(inBody('[data-testid="environment-live"]')!.className).toContain('v-btn--active')

    await click('environment-development')
    expect(environment.chosenEnvironment()).toBe('development')
    expect(inBody('[data-testid="environment-development"]')!.className).toContain('v-btn--active')

    const login = vi.spyOn(useAuthStore(), 'login').mockResolvedValue()
    await wrapper.find('form').trigger('submit')
    await settle()
    expect(login).toHaveBeenCalled()
    expect(router.currentRoute.value.name).toBe('home')
    wrapper.unmount()
  })

  it('opens on the environment the server is using (the last one chosen)', async () => {
    const { wrapper } = await mountLogin(['live', 'development'], 'development')
    expect(inBody('[data-testid="environment-development"]')!.className).toContain('v-btn--active')
    wrapper.unmount()
  })

  it('an environment not given to the user: a warning with the reason (not "invalid")', async () => {
    const { wrapper } = await mountLogin(['live', 'development'], 'development')
    vi.spyOn(useAuthStore(), 'login').mockRejectedValue(
      new ApiError(
        403,
        'The Development (Test) environment is not available to you. The administrators were told about this attempt.',
        { code: 'environment_denied' },
      ),
    )
    await wrapper.find('form').trigger('submit')
    await settle()
    const alert = inBody('[data-testid="login-error"]')!
    expect(alert.textContent).toContain('is not available to you')
    expect(alert.querySelector('.v-alert')!.className).toContain('text-warning')
    wrapper.unmount()
  })
})
