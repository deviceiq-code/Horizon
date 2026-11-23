import { createPinia, setActivePinia } from 'pinia'
import { afterEach, beforeEach, describe, expect, it } from 'vitest'

import { setLanguage } from '@/i18n'
import { useSystemSettingsStore } from '@/stores/systemSettings'
import { inBody, mountWithPlugins, settle } from '@/test-utils'
import SystemSettingsView from '../SystemSettingsView.vue'

describe('SystemSettingsView', () => {
  beforeEach(() => {
    setLanguage('en')
    setActivePinia(createPinia())
    useSystemSettingsStore().settings = {
      photo_search_enabled: true,
      searxng_url: 'http://192.168.0.22:30053',
    }
  })
  afterEach(() => {
    document.body.innerHTML = ''
  })

  it('shows every global setting', async () => {
    const wrapper = mountWithPlugins(SystemSettingsView)
    await settle()
    expect(inBody('h1')!.textContent).toBe('System Settings')
    // How users are shown is each user's own setting now (Settings)
    expect(inBody('[data-testid="user-name-display"]')).toBeNull()
    expect(inBody('[data-testid="system-settings"]')).not.toBeNull()
    wrapper.unmount()
  })
})
