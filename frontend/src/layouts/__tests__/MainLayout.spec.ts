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
import { useNotificationsStore } from '@/stores/notifications'
import { usePreferencesStore, type UiState } from '@/stores/preferences'
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
  email: 'fernando@example.com',
  role_refs: [{ name: 'Administrator', key: 'administrator', is_system: true }],
  preferences: {
    language: 'en',
    theme: 'system',
    color_theme: 'metallic_foundations',
    ui_scale: 'auto',
    date_format: 'auto',
    time_format: 'auto',
    select_on_focus: true,
    auto_scope: true,
    scope_threshold: '5.00',
    number_format: 'auto',
    percent_places: 2,
    currency: 'BRL',
    currency_display: 'symbol',
    ui_state: {},
    web_search_engine: 'google',
    updated_at: '',
  },
}

async function mountLayout(path = '/', uiState: UiState = {}) {
  const pinia = createPinia()
  setActivePinia(pinia)
  usePreferencesStore().apply({ ui_state: uiState })
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

  it("the user's menu: who they are and their roles, Settings and Sign out", async () => {
    const { wrapper, auth, router } = await mountLayout()
    const me = inBody('[data-testid="me"]')!
    expect(me.textContent).toContain('Fernando Almeida')
    expect(me.querySelector('img')!.getAttribute('src')).toBe('/api/users/1/photo/?v=abc')
    expect(inBody('header')!.textContent).not.toContain('Sign out')

    const logout = vi.spyOn(auth, 'logout').mockResolvedValue()
    await click('me')
    const menu = inBody('[data-testid="user-menu"]')!
    expect(menu.textContent).toContain('fernando@example.com')
    // System roles show translated
    expect(
      [...menu.querySelectorAll('[data-testid="user-role"]')].map((c) => c.textContent!.trim()),
    ).toEqual(['Administrator'])
    for (const item of ['Profile', 'Settings', 'Help & Support', 'Sign out']) {
      expect(menu.textContent).toContain(item)
    }
    await click('logout')
    expect(logout).toHaveBeenCalled()
    await settle()
    expect(router.currentRoute.value.name).toBe('login')
    wrapper.unmount()
  })

  it('the top bar switches light/dark and the language (saved to the account)', async () => {
    const { wrapper } = await mountLayout()
    const preferences = usePreferencesStore()
    const save = vi.spyOn(preferences, 'save').mockResolvedValue()
    // Light now: the button turns it dark
    await click('theme-switch')
    expect(save).toHaveBeenCalledWith({ theme: 'dark' })
    // The language: its code on the bar; each language by its own name in the menu
    expect(inBody('[data-testid="language"]')!.textContent).toContain('EN')
    await click('language')
    expect(inBody('[data-testid="language-menu"]')!.textContent).toContain('Português (Brasil)')
    expect(inBody('[data-testid="language-en"]')!.className).toContain('v-list-item--active')
    await click('language-pt-br')
    expect(save).toHaveBeenCalledWith({ language: 'pt-br' })
    wrapper.unmount()
  })

  it('search, documentation and notifications are coming soon', async () => {
    const { wrapper } = await mountLayout()
    await click('search')
    expect(useNotificationsStore().text).toBe('Search: coming soon.')
    await click('notifications')
    expect(useNotificationsStore().text).toBe('Notifications: coming soon.')
    wrapper.unmount()
  })

  it('outside an app: the Horizon brand and the apps in the side menu', async () => {
    const { wrapper } = await mountLayout('/')
    expect(inBody('[data-testid="brand"]')!.textContent).toContain('Horizon')
    expect(inBody('[data-testid="app-title"]')).toBeNull()
    expect(inBody('[data-testid="menu-app-pricing"]')).not.toBeNull()
    expect(inBody('[data-testid="menu-app-admin"]')).not.toBeNull()
    expect(inBody('[data-testid="menu-app-remarketing"]')).toBeNull() // coming soon
    expect(inBody('[data-testid="menu-app-partners"]')).toBeNull()
    wrapper.unmount()
  })

  it('inside an app: its name, its pages in the side menu and the path', async () => {
    const { wrapper } = await mountLayout('/admin/catalogs/asset-classes')
    // Administration's pages in two sections: Management and Catalogs
    expect(inBody('[data-testid="app-title"]')!.textContent!.trim()).toBe('Management')
    expect(inBody('[data-testid="section-menu.sections.catalogs"]')!.textContent!.trim()).toBe(
      'Catalogs',
    )
    expect(inBody('[data-testid="menu-roles"]')).not.toBeNull()
    expect(inBody('[data-testid="menu-catalogs-asset-classes"]')).not.toBeNull()
    expect(inBody('[data-testid="menu-customers"]')).not.toBeNull()
    expect(inBody('[data-testid="menu-users"]')).not.toBeNull()
    expect(inBody('[data-testid="menu-average-prices"]')).toBeNull()
    // The other apps, to switch to; not the current one
    expect(inBody('[data-testid="menu-app-pricing"]')).not.toBeNull()
    expect(inBody('[data-testid="menu-app-admin"]')).toBeNull()
    // The path is in the top bar
    expect(inBody('header [data-testid="breadcrumbs"]')!.textContent).toMatch(
      /Horizon.*Administration.*Asset Classes/,
    )
    wrapper.unmount()
  })

  it('the side menu collapses or opens and remembers the choice with the account', async () => {
    // jsdom's window is 1024 px wide: narrower than 1440, so the menu starts collapsed
    const { wrapper } = await mountLayout('/pricing/average-prices')
    const fetch = vi.spyOn(globalThis, 'fetch').mockResolvedValue(new Response('{}'))
    const menu = () => inBody('[data-testid="side-menu"]')!
    expect(menu().className).toContain('v-navigation-drawer--rail')
    await click('toggle-menu')
    expect(menu().className).not.toContain('v-navigation-drawer--rail')
    // Saved to the account: the same on any computer
    const [url, init] = fetch.mock.calls[0]!
    expect(String(url)).toContain('/api/auth/preferences/')
    expect(JSON.parse(String(init!.body))).toEqual({ ui_state: { sideMenu: { narrow: 'open' } } })
    wrapper.unmount()
    // Signed in again (e.g. elsewhere): as the user left it
    const again = await mountLayout('/pricing/average-prices', { sideMenu: { narrow: 'open' } })
    expect(menu().className).not.toContain('v-navigation-drawer--rail')
    again.wrapper.unmount()
  })

  it('the app launcher lists the apps; Remarketing is coming soon', async () => {
    const { wrapper } = await mountLayout('/pricing/average-prices')
    expect(inBody('[data-testid="app-title"]')!.textContent!.trim()).toBe('Pricing')
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
