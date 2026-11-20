import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { h } from 'vue'
import { createMemoryHistory, createRouter } from 'vue-router'
import { VApp } from 'vuetify/components'

import { i18n, setLanguage } from '@/i18n'
import vuetify from '@/plugins/vuetify'
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
    updated_at: '',
  },
}

async function mountLayout() {
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
      ...['average-prices', 'customers', 'account-managers', 'catalogs', 'users'].map((name) => ({
        path: `/${name}`,
        name,
        component: Blank,
      })),
    ],
  })
  await router.push('/')
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
})
