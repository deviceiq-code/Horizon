import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { afterEach, beforeEach, describe, expect, it } from 'vitest'
import { createMemoryHistory, createRouter } from 'vue-router'

import { i18n, setLanguage } from '@/i18n'
import vuetify from '@/plugins/vuetify'
import { useAuthStore, type User } from '@/stores/auth'
import { useSystemSettingsStore } from '@/stores/systemSettings'
import { inBody, settle } from '@/test-utils'
import SettingsView from '../SettingsView.vue'

const user = (is_admin: boolean): User => ({
  id: 1,
  username: 'fernando',
  name: 'Fernando',
  is_admin,
  roles: is_admin ? ['Administrator'] : [],
  photo_version: null,
  preferences: { language: 'en', theme: 'system', updated_at: '' },
})

async function mountAt(path: string, isStaff: boolean) {
  const pinia = createPinia()
  setActivePinia(pinia)
  useAuthStore().user = user(isStaff)
  useSystemSettingsStore().settings = {
    photo_search_enabled: true,
    user_name_display: 'full_name',
    full_name_order: 'first_last',
    searxng_url: 'http://192.168.0.22:30053',
  }
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [{ path: '/settings', name: 'settings', component: SettingsView }],
  })
  await router.push(path)
  const wrapper = mount(SettingsView, {
    attachTo: document.body,
    global: { plugins: [vuetify, i18n, pinia, router] },
  })
  await settle()
  return { wrapper, router }
}

describe('SettingsView', () => {
  beforeEach(() => setLanguage('en'))
  afterEach(() => {
    document.body.innerHTML = ''
  })

  it('administrators get the user and the system tabs', async () => {
    const { wrapper, router } = await mountAt('/settings', true)
    expect(inBody('[data-testid="tab-user"]')!.textContent).toContain('User settings')
    expect(inBody('[data-testid="tab-system"]')!.textContent).toContain('System settings')
    // User settings first
    expect(inBody('[data-testid="language-select"]')).not.toBeNull()
    expect(inBody('[data-testid="system-settings"]')).toBeNull()

    inBody('[data-testid="tab-system"]')!.click()
    await settle()
    expect(router.currentRoute.value.query.tab).toBe('system')
    expect(inBody('[data-testid="system-settings"]')).not.toBeNull()
    expect((inBody('[data-testid="searxng-url"] input') as HTMLInputElement).value).toBe(
      'http://192.168.0.22:30053',
    )
    wrapper.unmount()
  })

  it('opens on the tab in the address', async () => {
    const { wrapper } = await mountAt('/settings?tab=system', true)
    expect(inBody('[data-testid="system-settings"]')).not.toBeNull()
    wrapper.unmount()
  })

  it('other users only have their own settings', async () => {
    const { wrapper } = await mountAt('/settings?tab=system', false)
    expect(inBody('[data-testid="tab-system"]')).toBeNull()
    expect(inBody('[data-testid="system-settings"]')).toBeNull()
    expect(inBody('[data-testid="language-select"]')).not.toBeNull()
    wrapper.unmount()
  })
})
