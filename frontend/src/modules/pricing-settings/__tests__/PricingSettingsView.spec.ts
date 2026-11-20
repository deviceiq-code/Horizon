import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

import { setLanguage } from '@/i18n'
import { click, inBody, mountWithPlugins, settle, typeInto } from '@/test-utils'
import * as settingsApi from '../api'
import PricingSettingsView from '../PricingSettingsView.vue'

vi.mock('../api', () => ({
  getPricingSettings: vi.fn<typeof settingsApi.getPricingSettings>(),
  updatePricingSettings: vi.fn<typeof settingsApi.updatePricingSettings>(),
}))
const api = vi.mocked(settingsApi)

const SETTINGS: settingsApi.PricingSettings = {
  compatible_percent: '5.00',
  below_percent: '10.00',
  above_percent: '10.00',
  validity_months: 12,
  accept_expired: true,
  updated_at: '2026-11-20T10:00:00Z',
  updated_by_name: 'Fernando Almeida',
}

const value = (testId: string) =>
  (inBody(`[data-testid="${testId}"] input`) as HTMLInputElement).value

describe('PricingSettingsView', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    setLanguage('pt-br')
    api.getPricingSettings.mockResolvedValue(SETTINGS)
  })
  afterEach(() => {
    vi.clearAllMocks()
    document.body.innerHTML = ''
  })

  it('shows the limits and the scale they make', async () => {
    const wrapper = mountWithPlugins(PricingSettingsView)
    await settle()
    expect([value('below'), value('compatible'), value('above'), value('validity-months')]).toEqual(
      ['10,00', '5,00', '10,00', '12'],
    )
    const scale = inBody('[data-testid="scale"]')!.textContent!.replace(/\s+/g, ' ')
    expect(scale).toContain('Abaixo do Histórico')
    expect(scale).toContain('± 5,00%')
    expect(scale).toContain('≥ +10,00%')
    wrapper.unmount()
  })

  it('saves decimals typed with a comma', async () => {
    api.updatePricingSettings.mockResolvedValue({ ...SETTINGS, below_percent: '7.50' })
    const wrapper = mountWithPlugins(PricingSettingsView)
    await settle()
    await typeInto('below', '7,5')
    await typeInto('validity-months', '18')
    ;(inBody('[data-testid="accept-expired"] input') as HTMLInputElement).click()
    await settle()
    await click('save')
    expect(api.updatePricingSettings).toHaveBeenCalledWith({
      compatible_percent: '5.00',
      below_percent: '7.5',
      above_percent: '10.00',
      validity_months: 18,
      accept_expired: false,
    })
    wrapper.unmount()
  })

  it('the limits must be beyond the compatible range', async () => {
    const wrapper = mountWithPlugins(PricingSettingsView)
    await settle()
    await typeInto('above', '4')
    await click('save')
    expect(api.updatePricingSettings).not.toHaveBeenCalled()
    expect(inBody('[data-testid="above"]')!.textContent).toContain('maior que a faixa compatível')
    wrapper.unmount()
  })
})
