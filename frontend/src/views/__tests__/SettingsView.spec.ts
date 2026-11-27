import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createMemoryHistory, createRouter } from 'vue-router'

import { i18n, setLanguage } from '@/i18n'
import vuetify from '@/plugins/vuetify'
import { useAuthStore, type User } from '@/stores/auth'
import { usePreferencesStore } from '@/stores/preferences'
import { click, inBody, pickOption, settle, typeInto } from '@/test-utils'
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
    color_theme: 'emerald_slate',
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
    user_name_display: 'full_name',
    full_name_order: 'first_last',
    searxng_url: '',
    web_search: true,
    web_search_engine: 'google',
    updated_at: '',
  },
})

async function mountAt(path: string, isStaff: boolean) {
  const pinia = createPinia()
  setActivePinia(pinia)
  useAuthStore().user = user(isStaff)
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

  it('offers the color themes, Emerald Slate first and chosen by default', async () => {
    const { wrapper } = await mountAt('/settings', false)
    const card = inBody('[data-testid="color-theme-emerald_slate"]')!
    expect(card.textContent).toContain('Emerald Slate')
    expect(card.getAttribute('aria-pressed')).toBe('true')
    expect(inBody('[data-testid^="color-theme-"]')!.getAttribute('data-testid')).toBe(
      'color-theme-emerald_slate',
    )
    // A row of its own: title and description, the themes below
    expect(inBody('[data-testid="color-themes"]')!.closest('.setting-row')!.textContent).toContain(
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

  it('how users are shown: each user chooses; the top bar follows', async () => {
    const { wrapper } = await mountAt('/settings?tab=appearance', false)
    const preferences = usePreferencesStore()
    const save = vi.spyOn(preferences, 'save').mockResolvedValue()
    const refresh = vi.spyOn(useAuthStore(), 'refresh').mockResolvedValue()
    const example = () => inBody('[data-testid="name-example"]')!.textContent!
    expect(example()).toContain('Maria Silva')
    await click('name-display-first_name')
    expect(save).toHaveBeenCalledWith({ user_name_display: 'first_name' })
    expect(refresh).toHaveBeenCalled()
    preferences.apply({ user_name_display: 'full_name', full_name_order: 'last_first' })
    await settle()
    expect(example()).toContain('Silva, Maria')
    // The order belongs under "Show Users by", with no separator
    const order = inBody('[data-testid="name-order"]')!.closest('.setting-row')!
    expect(order.className).toContain('setting-row--child')
    wrapper.unmount()
  })

  it('photo search is part of Internet Search: its SearXNG address, saved when left, and a test', async () => {
    const { wrapper } = await mountAt('/settings?tab=smartTools', false)
    const preferences = usePreferencesStore()
    const save = vi.spyOn(preferences, 'save').mockResolvedValue()
    const test = vi.spyOn(preferences, 'testSearxng').mockResolvedValue({ results: 12 })
    // No switch of its own: it follows Internet Search
    expect(inBody('[data-testid="photo-search-switch"]')).toBeNull()
    await typeInto('searxng-url', 'http://192.168.0.22:30053')
    await click('searxng-test')
    expect(test).toHaveBeenCalledWith('http://192.168.0.22:30053')
    expect(inBody('[data-testid="searxng-test-result"]')!.textContent).toContain('12 images')
    inBody('[data-testid="searxng-url"] input')!.dispatchEvent(new Event('blur'))
    await settle()
    expect(save).toHaveBeenCalledWith({ searxng_url: 'http://192.168.0.22:30053' })
    // Internet Search off: photo search too — still shown, disabled
    preferences.apply({ web_search: false })
    await settle()
    const address = inBody('[data-testid="searxng-url"]')!
    expect(address.closest('.setting-row')!.className).toContain('setting-row--disabled')
    expect(address.className).toContain('v-input--disabled')
    expect(inBody('[data-testid="web-search-engine"]')!.className).toContain('v-input--disabled')
    preferences.apply({ web_search: true })
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
    expect(card.previousElementSibling!.textContent).toContain('Smart Tools')
    expect(card.textContent).toContain('Select on Focus')
    const toggle = inBody('[data-testid="select-on-focus"] input') as HTMLInputElement
    expect(toggle.checked).toBe(true)
    toggle.click()
    await settle()
    expect(save).toHaveBeenCalledWith({ select_on_focus: false })
    wrapper.unmount()
  })
})
