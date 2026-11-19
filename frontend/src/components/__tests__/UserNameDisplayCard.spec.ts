import { createPinia, setActivePinia } from 'pinia'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { setLanguage } from '@/i18n'
import { useAuthStore } from '@/stores/auth'
import { useNotificationsStore } from '@/stores/notifications'
import { useSystemSettingsStore } from '@/stores/systemSettings'
import { click, inBody, mountWithPlugins, settle } from '@/test-utils'
import UserNameDisplayCard from '../UserNameDisplayCard.vue'

function choose(group: string, value: string) {
  const radio = inBody(`[data-testid="${group}"] input[value="${value}"]`) as HTMLInputElement
  radio.click()
  return settle()
}

const example = () => inBody('[data-testid="name-example"]')!.textContent?.trim()

describe('UserNameDisplayCard', () => {
  let store: ReturnType<typeof useSystemSettingsStore>

  beforeEach(() => {
    setLanguage('en')
    setActivePinia(createPinia())
    store = useSystemSettingsStore()
    store.settings = {
      photo_search_enabled: false,
      user_name_display: 'full_name',
      full_name_order: 'first_last',
    }
  })

  afterEach(() => {
    vi.restoreAllMocks()
    document.body.innerHTML = ''
  })

  it('shows an example of each choice and saves it', async () => {
    const save = vi.spyOn(store, 'save').mockResolvedValue(store.settings!)
    const refresh = vi.spyOn(useAuthStore(), 'refresh').mockResolvedValue()
    const wrapper = mountWithPlugins(UserNameDisplayCard)
    await settle()

    expect(example()).toBe('Maria Silva')
    await choose('name-order', 'last_first')
    expect(example()).toBe('Silva, Maria')
    await choose('name-display', 'first_name')
    expect(example()).toBe('Maria')
    await choose('name-display', 'username')
    expect(example()).toBe('msilva')
    // The order only matters for full names
    expect(
      (inBody('[data-testid="name-order"] input[value="first_last"]') as HTMLInputElement).disabled,
    ).toBe(true)

    await choose('name-display', 'full_name')
    await click('name-save')
    expect(save).toHaveBeenCalledWith({
      user_name_display: 'full_name',
      full_name_order: 'last_first',
    })
    expect(refresh).toHaveBeenCalled() // the top bar follows the new format
    expect(useNotificationsStore().text).toBe('System settings saved.')
    wrapper.unmount()
  })
})
