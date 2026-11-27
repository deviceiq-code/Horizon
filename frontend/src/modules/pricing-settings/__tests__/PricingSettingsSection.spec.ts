import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

import { ApiError } from '@/api'
import { setLanguage } from '@/i18n'
import { useNotificationsStore } from '@/stores/notifications'
import { inBody, mountWithPlugins, settle, typeInto } from '@/test-utils'
import * as settingsApi from '../api'
import PricingSettingsSection from '../PricingSettingsSection.vue'

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

const input = (testId: string) => inBody(`[data-testid="${testId}"] input`) as HTMLInputElement
/** Type into a field and leave it (where it is saved) */
async function typeAndLeave(testId: string, value: string) {
  await typeInto(testId, value)
  input(testId).dispatchEvent(new Event('blur'))
  await settle()
}

describe('PricingSettingsSection', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    setLanguage('pt-br')
    api.getPricingSettings.mockResolvedValue(SETTINGS)
  })
  afterEach(() => {
    vi.clearAllMocks()
    document.body.innerHTML = ''
  })

  it('shows the limits, the scale they make and the last change', async () => {
    const wrapper = mountWithPlugins(PricingSettingsSection)
    await settle()
    expect(
      ['below', 'compatible', 'above', 'validity-months'].map((id) => input(id).value),
    ).toEqual(['10,00', '5,00', '10,00', '12'])
    const scale = inBody('[data-testid="scale"]')!.textContent!.replace(/\s+/g, ' ')
    expect(scale).toContain('Abaixo do Histórico')
    expect(scale).toContain('± 5,00%')
    expect(scale).toContain('≥ +10,00%')
    expect(inBody('[data-testid="pricing-last-change"]')!.textContent).toContain('Fernando Almeida')
    wrapper.unmount()
  })

  it('saves each change on its own: a field when left (decimals with a comma), the switch at once', async () => {
    api.updatePricingSettings.mockResolvedValueOnce({ ...SETTINGS, below_percent: '7.50' })
    const wrapper = mountWithPlugins(PricingSettingsSection)
    await settle()
    await typeAndLeave('below', '7,5')
    expect(api.updatePricingSettings).toHaveBeenLastCalledWith({ below_percent: '7.5' })
    expect(input('below').value).toBe('7,50')
    expect(useNotificationsStore().color).toBe('success')

    // Leaving a field unchanged saves nothing
    input('compatible').dispatchEvent(new Event('blur'))
    await settle()
    expect(api.updatePricingSettings).toHaveBeenCalledTimes(1)

    api.updatePricingSettings.mockResolvedValueOnce({ ...SETTINGS, validity_months: 18 })
    await typeAndLeave('validity-months', '18')
    expect(api.updatePricingSettings).toHaveBeenLastCalledWith({ validity_months: 18 })

    api.updatePricingSettings.mockResolvedValueOnce({ ...SETTINGS, accept_expired: false })
    input('accept-expired').click()
    await settle()
    expect(api.updatePricingSettings).toHaveBeenLastCalledWith({ accept_expired: false })
    expect(inBody('[data-testid="accept-expired-hint"]')!.textContent).toContain('recusam')
    wrapper.unmount()
  })

  it('the limits must be beyond the compatible range: not saved, the reason shown', async () => {
    const wrapper = mountWithPlugins(PricingSettingsSection)
    await settle()
    await typeAndLeave('above', '4')
    expect(inBody('[data-testid="above"]')!.textContent).toContain('maior que a faixa compatível')
    await typeAndLeave('compatible', '12')
    expect(inBody('[data-testid="compatible"]')!.textContent).toContain('menor que os limites')
    expect(api.updatePricingSettings).not.toHaveBeenCalled()
    wrapper.unmount()
  })

  it("shows the server's refusal on its field", async () => {
    api.updatePricingSettings.mockRejectedValue(
      new ApiError(400, 'Bad Request', {
        below_percent: ['Deve ser maior que a faixa compatível (5%).'],
      }),
    )
    const wrapper = mountWithPlugins(PricingSettingsSection)
    await settle()
    await typeAndLeave('below', '8')
    expect(inBody('[data-testid="below"]')!.textContent).toContain('(5%)')
    expect(useNotificationsStore().color).toBe('error')
    wrapper.unmount()
  })
})
