import { createPinia, setActivePinia } from 'pinia'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { ApiError } from '@/api'
import { setLanguage } from '@/i18n'
import { useNotificationsStore } from '@/stores/notifications'
import { useSystemSettingsStore } from '@/stores/systemSettings'
import { click, inBody, mountWithPlugins, settle, typeInto } from '@/test-utils'
import SystemSettingsCard from '../SystemSettingsCard.vue'

describe('SystemSettingsCard', () => {
  let store: ReturnType<typeof useSystemSettingsStore>

  beforeEach(() => {
    setLanguage('en')
    setActivePinia(createPinia())
    store = useSystemSettingsStore()
    store.settings = { photo_search_enabled: false, searxng_url: '' }
  })

  afterEach(() => {
    vi.restoreAllMocks()
    document.body.innerHTML = ''
  })

  it('tests and saves the SearXNG address', async () => {
    const test = vi.spyOn(store, 'testSearxng').mockResolvedValue({ results: 23 })
    const save = vi.spyOn(store, 'save').mockImplementation(async (changes) => {
      store.settings = { photo_search_enabled: true, searxng_url: 'http://192.168.0.22:30053' }
      expect(changes).toEqual({ searxng_url: 'http://192.168.0.22:30053/' })
      return store.settings
    })
    const wrapper = mountWithPlugins(SystemSettingsCard)
    await settle()

    await typeInto('searxng-url', 'http://192.168.0.22:30053/')
    await click('searxng-test')
    expect(test).toHaveBeenCalledWith('http://192.168.0.22:30053/')
    expect(inBody('[data-testid="searxng-test-result"]')!.textContent).toContain(
      'It works: 23 images found.',
    )

    await click('system-save')
    expect(save).toHaveBeenCalled()
    expect((inBody('[data-testid="searxng-url"] input') as HTMLInputElement).value).toBe(
      'http://192.168.0.22:30053',
    )
    expect(useNotificationsStore().text).toBe('System settings saved.')
    wrapper.unmount()
  })

  it('explains why a test failed', async () => {
    vi.spyOn(store, 'testSearxng').mockRejectedValue(
      new ApiError(502, 'SearXNG refused the JSON format. Enable it in its settings.yml.'),
    )
    const wrapper = mountWithPlugins(SystemSettingsCard)
    await settle()
    await typeInto('searxng-url', 'http://192.168.0.22:30053')
    await click('searxng-test')
    expect(inBody('[data-testid="searxng-test-result"]')!.textContent).toContain('settings.yml')
    wrapper.unmount()
  })
})
