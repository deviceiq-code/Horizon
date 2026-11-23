/**
 * System-wide settings (Settings page, administrators). Everyone logged in learns what is
 * enabled (e.g. photo search); administrators also get and change the values.
 */
import { ref } from 'vue'
import { defineStore } from 'pinia'
import { api } from '@/api'

export interface SystemSettings {
  photo_search_enabled: boolean
  /** Administrators only */
  searxng_url?: string
  updated_at?: string
}

export const useSystemSettingsStore = defineStore('systemSettings', () => {
  const settings = ref<SystemSettings | null>(null)
  let loading: Promise<SystemSettings> | null = null

  /** Loaded once per page (call `reload` after a change made elsewhere). */
  function load(): Promise<SystemSettings> {
    if (settings.value) return Promise.resolve(settings.value)
    loading ??= api<SystemSettings>('/system/settings/')
      .then((data) => (settings.value = data))
      .finally(() => (loading = null))
    return loading
  }

  async function save(changes: Partial<Pick<SystemSettings, 'searxng_url'>>) {
    settings.value = await api<SystemSettings>('/system/settings/', {
      method: 'PATCH',
      body: JSON.stringify(changes),
    })
    return settings.value
  }

  /** Try a search on a SearXNG address (not saved); resolves with how many images came. */
  function testSearxng(searxngUrl: string) {
    return api<{ results: number }>('/system/settings/test-searxng/', {
      method: 'POST',
      body: JSON.stringify({ searxng_url: searxngUrl }),
    })
  }

  return { settings, load, save, testSearxng }
})
