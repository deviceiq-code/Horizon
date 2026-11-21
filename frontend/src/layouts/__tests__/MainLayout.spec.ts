import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { h } from 'vue'
import { createMemoryHistory, createRouter } from 'vue-router'
import { VApp } from 'vuetify/components'

import { i18n, setLanguage } from '@/i18n'
import vuetify from '@/plugins/vuetify'
import { moduleRoutes } from '@/modules'
import { useAuthStore, type User } from '@/stores/auth'
import { usePreferencesStore } from '@/stores/preferences'
import { click, inBody, settle } from '@/test-utils'
import MainLayout from '../MainLayout.vue'

const Blank = { render: () => null }

const ME: User = {
  id: 1,
  username: 'fernando',
  name: 'Fernando Almeida',
  is_admin: true,
  roles: ['Administrator'],
  photo_version: 'abc',
  preferences: {
    language: 'en',
    theme: 'system',
    color_theme: 'metallic_foundations',
    ui_scale: 'auto',
    updated_at: '',
  },
}

async function mountLayout(path = '/') {
  const pinia = createPinia()
  setActivePinia(pinia)
  const auth = useAuthStore()
  auth.user = ME
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/', name: 'home', component: Blank },
      { path: '/login', name: 'login', component: Blank },
      { path: '/settings', name: 'settings', component: Blank },
      { path: '/', component: Blank, children: moduleRoutes() },
    ],
  })
  await router.push(path)
  // v-layout gives the app bar and drawer their place
  const wrapper = mount(
    { render: () => h(VApp, () => h(MainLayout)) },
    { attachTo: document.body, global: { plugins: [vuetify, i18n, pinia, router] } },
  )
  await settle()
  return { wrapper, auth, router }
}

describe('MainLayout', () => {
  beforeEach(() => setLanguage('en'))
  afterEach(() => {
    vi.restoreAllMocks()
    document.body.innerHTML = ''
  })

  it('the top bar shows only the user (photo and name); the menu signs out', async () => {
    const { wrapper, auth, router } = await mountLayout()
    const me = inBody('[data-testid="me"]')!
    expect(me.textContent).toContain('Fernando Almeida')
    expect(me.querySelector('img')!.getAttribute('src')).toBe('/api/users/1/photo/?v=abc')
    // No language selector nor sign-out button in the bar itself
    expect(inBody('header')!.textContent).not.toContain('Sign out')
    expect(inBody('header [aria-label="Select language"]')).toBeNull()

    const logout = vi.spyOn(auth, 'logout').mockResolvedValue()
    await click('me')
    expect(inBody('[data-testid="user-menu"]')!.textContent).toContain('Sign out')
    await click('logout')
    expect(logout).toHaveBeenCalled()
    await settle()
    expect(router.currentRoute.value.name).toBe('login')
    wrapper.unmount()
  })

  it('the user menu changes the appearance (saved to the account)', async () => {
    const { wrapper } = await mountLayout()
    const preferences = usePreferencesStore()
    preferences.theme = 'system'
    const save = vi.spyOn(preferences, 'save').mockResolvedValue()
    await click('me')
    const menu = inBody('[data-testid="user-menu"]')!
    expect(menu.textContent).toContain('Appearance')
    expect(inBody('[data-testid="theme-system"]')!.className).toContain('v-btn--active')

    await click('theme-dark')
    expect(save).toHaveBeenCalledWith({ theme: 'dark' })
    wrapper.unmount()
  })

  it('outside an app: "Horizon", the apps in the side menu', async () => {
    const { wrapper } = await mountLayout('/')
    expect(inBody('[data-testid="app-title"]')!.textContent).toBe('Horizon')
    expect(inBody('[data-testid="menu-app-pricing"]')).not.toBeNull()
    expect(inBody('[data-testid="menu-app-admin"]')).not.toBeNull()
    expect(inBody('[data-testid="menu-app-remarketing"]')).toBeNull() // coming soon
    expect(inBody('[data-testid="menu-app-partners"]')).toBeNull()
    wrapper.unmount()
  })

  it('inside an app: its name, its pages in the side menu and the path', async () => {
    const { wrapper } = await mountLayout('/admin/catalogs/asset-classes')
    expect(inBody('[data-testid="app-title"]')!.textContent).toBe('Administration')
    expect(inBody('[data-testid="menu-customers"]')).not.toBeNull()
    expect(inBody('[data-testid="menu-users"]')).not.toBeNull()
    expect(inBody('[data-testid="menu-average-prices"]')).toBeNull()
    expect(inBody('[data-testid="breadcrumbs"]')!.textContent).toMatch(
      /Horizon.*Administration.*Catalogs.*Asset Classes/,
    )
    wrapper.unmount()
  })

  it('the app launcher lists the apps; Remarketing is coming soon', async () => {
    const { wrapper } = await mountLayout('/pricing/average-prices')
    expect(inBody('[data-testid="app-title"]')!.textContent).toBe('Pricing')
    await click('app-launcher')
    const menu = inBody('[data-testid="app-launcher-menu"]')!
    expect(menu.textContent).toContain('Pricing')
    expect(menu.textContent).toContain('Coming Soon')
    expect(inBody('[data-testid="launcher-remarketing"]')!.className).toContain(
      'v-list-item--disabled',
    )
    expect(inBody('[data-testid="launcher-pricing"]')!.className).toContain('v-list-item--active')
    wrapper.unmount()
  })

  it("the user menu opens the user's settings", async () => {
    const { wrapper, router } = await mountLayout('/pricing/average-prices')
    await click('me')
    await click('user-settings')
    await settle()
    expect(router.currentRoute.value.name).toBe('settings')
    wrapper.unmount()
  })
})
