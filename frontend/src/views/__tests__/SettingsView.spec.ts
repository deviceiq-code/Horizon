import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createMemoryHistory, createRouter } from 'vue-router'

import { i18n, setLanguage } from '@/i18n'
import vuetify from '@/plugins/vuetify'
import { useAuthStore, type User } from '@/stores/auth'
import { usePreferencesStore } from '@/stores/preferences'
import { useSystemSettingsStore } from '@/stores/systemSettings'
import { click, inBody, pickOption, settle } from '@/test-utils'
import SettingsView from '../SettingsView.vue'

const user = (is_admin: boolean): User => ({
  id: 1,
  username: 'fernando',
  name: 'Fernando',
  is_admin,
  roles: is_admin ? ['Administrator'] : [],
  photo_version: null,
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
    web_search: true,
    web_search_engine: 'google',
    updated_at: '',
  },
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

  it("has only the user's own settings (global ones are in Administration)", async () => {
    const { wrapper } = await mountAt('/settings', true)
    expect(inBody('[data-testid="language-select"]')).not.toBeNull()
    expect(inBody('[data-testid="theme-toggle"]')).not.toBeNull()
    expect(inBody('[data-testid="system-settings"]')).toBeNull()
    expect(inBody('[data-testid="settings-tabs"]')).toBeNull()
    wrapper.unmount()
  })

  it('offers the color themes, Metallic Foundations chosen by default', async () => {
    const { wrapper } = await mountAt('/settings', false)
    const card = inBody('[data-testid="color-theme-metallic_foundations"]')!
    expect(card.textContent).toContain('Metallic Foundations')
    expect(card.getAttribute('aria-pressed')).toBe('true')
    expect(inBody('[data-testid="color-themes"]')!.previousElementSibling!.textContent).toContain(
      'Color Theme',
    )
    wrapper.unmount()
  })

  it('offers the interface size, automatic by default', async () => {
    const { wrapper } = await mountAt('/settings', false)
    const preferences = usePreferencesStore()
    const save = vi.spyOn(preferences, 'save').mockResolvedValue()
    expect(inBody('[data-testid="ui-scale-auto"]')!.className).toContain('v-btn--active')
    expect(inBody('[data-testid="ui-scale-hint"]')!.textContent).toMatch(/now \d+%/)
    await click('ui-scale-small')
    expect(save).toHaveBeenCalledWith({ ui_scale: 'small' })
    wrapper.unmount()
  })

  it('changes the date and time formats, with an example', async () => {
    const { wrapper } = await mountAt('/settings', false)
    const preferences = usePreferencesStore()
    const save = vi.spyOn(preferences, 'save').mockResolvedValue()
    expect(inBody('[data-testid="date-format-auto"]')!.className).toContain('v-btn--active')
    await click('date-format-ymd')
    expect(save).toHaveBeenCalledWith({ date_format: 'ymd' })
    await click('time-format-24h')
    expect(save).toHaveBeenCalledWith({ time_format: '24h' })
    // The example follows the formats in use
    preferences.apply({ date_format: 'ymd', time_format: '24h' })
    await settle()
    expect(inBody('[data-testid="date-time-example"]')!.textContent).toMatch(
      /Now: \d{4}-\d{2}-\d{2}, \d{2}:\d{2}/,
    )
    wrapper.unmount()
  })

  it('in tabs; the open one is in the address', async () => {
    const { wrapper, router } = await mountAt('/settings', false)
    const active = () => inBody('[data-testid="settings-sections"] .v-tab--selected')!.textContent
    expect(active()).toContain('Language and Region')
    await click('tab-appearance')
    await settle()
    expect(router.currentRoute.value.query.tab).toBe('appearance')
    expect(active()).toContain('Appearance')
    wrapper.unmount()
    const again = await mountAt('/settings?tab=smartTools', false)
    expect(active()).toContain('Smart Tools')
    again.wrapper.unmount()
  })

  it('numbers and currency: the format, the currency (symbol and code) and how it shows', async () => {
    const { wrapper } = await mountAt('/settings', false)
    const preferences = usePreferencesStore()
    const save = vi.spyOn(preferences, 'save').mockResolvedValue()
    const example = () => inBody('[data-testid="numbers-example"]')!.textContent!
    expect(example()).toMatch(/R\$\s?1,234,567\.89/)
    expect(inBody('[data-testid="currency-symbol"]')!.textContent).toContain('R$')
    expect(inBody('[data-testid="currency-code"]')!.textContent).toContain('BRL')
    await click('number-format-dot_comma')
    expect(save).toHaveBeenCalledWith({ number_format: 'dot_comma' })
    await pickOption('currency', 'Euro (EUR)')
    expect(save).toHaveBeenCalledWith({ currency: 'EUR' })
    await click('currency-display-code')
    expect(save).toHaveBeenCalledWith({ currency_display: 'code' })
    await click('percent-places-4')
    expect(save).toHaveBeenCalledWith({ percent_places: 4 })
    expect(inBody('[data-testid="percent-example"]')!.textContent).toContain('12.35%')
    // What is shown follows them at once
    preferences.apply({ number_format: 'dot_comma', currency: 'EUR', currency_display: 'code' })
    await settle()
    expect(example()).toMatch(/EUR\s1\.234\.567,89/)
    expect(inBody('[data-testid="currency-code"]')!.textContent).toContain('EUR')
    expect(inBody('[data-testid="currency-display-symbol"]')!.textContent).toContain('Symbol (€)')
    // Every percentage follows the decimal places chosen
    preferences.apply({ percent_places: 4 })
    await settle()
    expect(inBody('[data-testid="percent-example"]')!.textContent).toContain('12,3457%')
    preferences.apply({ percent_places: 2 })
    preferences.apply({ number_format: 'auto', currency: 'BRL', currency_display: 'symbol' })
    wrapper.unmount()
  })

  it('Smart Tools: select on focus, on by default, can be turned off', async () => {
    const { wrapper } = await mountAt('/settings', false)
    const preferences = usePreferencesStore()
    const save = vi.spyOn(preferences, 'save').mockResolvedValue()
    const card = inBody('[data-testid="smart-tools"]')!
    expect(card.textContent).toContain('Smart Tools')
    expect(card.textContent).toContain('Select on Focus')
    const toggle = inBody('[data-testid="select-on-focus"] input') as HTMLInputElement
    expect(toggle.checked).toBe(true)
    toggle.click()
    await settle()
    expect(save).toHaveBeenCalledWith({ select_on_focus: false })
    wrapper.unmount()
  })
})
