import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { i18n, setLanguage } from '@/i18n'
import * as settingsApi from '@/modules/pricing-settings/api'
import * as html from '@/utils/html'
import vuetify from '@/plugins/vuetify'
import { inBody, pickOption, settle } from '@/test-utils'
import * as efmvApi from '../api'
import ReportDialog from '../ReportDialog.vue'

vi.mock('../api', async (importOriginal) => ({
  ...(await importOriginal<typeof import('../api')>()),
  getEfmvAnalysis: vi.fn<typeof efmvApi.getEfmvAnalysis>(),
}))
vi.mock('@/utils/html', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@/utils/html')>()),
  printDocument: vi.fn<(html: string) => void>(),
}))
vi.mock('@/modules/pricing-settings/api', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@/modules/pricing-settings/api')>()),
  getPricingSettings: vi.fn<typeof settingsApi.getPricingSettings>(),
}))

const TOTALS = {
  lo: '1000.00',
  efmv_total: '150.00',
  efmv_percent: '15.00000',
  hw_percent: '100.00000',
  sw_percent: null,
  sv_percent: null,
  hw_total: '1000.00',
  sw_total: '0.00',
  sv_total: '0.00',
}
const scenario = (id: number, title: string, term = 36) => ({
  id,
  name: '',
  title,
  term_months: term,
  scope: 'Fleet',
  scope_suggestion: '',
  items: [],
  totals: TOTALS,
  has_expired: false,
})

describe('printing an analysis', () => {
  beforeEach(() => {
    setLanguage('pt-br')
    setActivePinia(createPinia())
    vi.mocked(efmvApi).getEfmvAnalysis.mockResolvedValue({
      id: 3,
      code: 'EFMV-2026-0661',
      account_manager_detail: { id: 1, full_name: 'Ana Lima' },
      customer_detail: { id: 2, name: 'IHM Engenharia', trade_name: '', tax_id: '' },
      vertical_label: 'TI',
      created_by_name: 'Bruno Reis',
      created_at: '2026-11-20T10:00:00Z',
      updated_by_name: 'Carla Dias',
      updated_at: '2026-11-25T10:00:00Z',
      scenarios: [scenario(10, '36 Meses', 36), scenario(11, '48 Meses', 48)],
    } as unknown as efmvApi.EfmvAnalysis)
    vi.mocked(settingsApi).getPricingSettings.mockResolvedValue({
      report_disclaimer: {
        en: 'Note',
        'pt-br': 'Atenção: inclua [{code}].',
        es: 'Nota: [{code}].',
      },
    } as unknown as settingsApi.PricingSettings)
  })
  afterEach(() => {
    vi.clearAllMocks()
    document.body.innerHTML = ''
    setLanguage('en')
  })

  it('previews the scenarios chosen with the disclaimer in the user’s language', async () => {
    const wrapper = mount(ReportDialog, {
      props: { modelValue: false, analysisId: 3 },
      attachTo: document.body,
      global: { plugins: [vuetify, i18n] },
    })
    await wrapper.setProps({ modelValue: true })
    await settle()
    const preview = () => inBody('[data-testid="report-preview"]') as HTMLIFrameElement
    expect(preview().srcdoc).toContain('36 Meses')
    expect(preview().srcdoc).toContain('48 Meses')
    expect(preview().srcdoc).toContain('Atenção: inclua [EFMV-2026-0661].')
    // One scenario left out
    ;(inBody('[data-testid="report-scenario-11"] input') as HTMLInputElement).click()
    await settle()
    expect(preview().srcdoc).not.toContain('48 Meses')
    // Prints that same frame
    // …with the page titled as the file the PDF is suggested to be, restored afterwards
    document.title = 'Horizon'
    let titleWhilePrinting = ''
    const print = vi.fn<() => void>(() => {
      titleWhilePrinting = document.title
    })
    Object.defineProperty(preview(), 'contentWindow', {
      value: { focus: vi.fn<() => void>(), print },
    })
    vi.useFakeTimers()
    ;(inBody('[data-testid="report-print"]') as HTMLButtonElement).click()
    expect(print).toHaveBeenCalled()
    expect(titleWhilePrinting).toBe('EFMV-2026-0661 - IHM Engenharia - TI')
    window.dispatchEvent(new Event('afterprint'))
    expect(document.title).toBe('Horizon')
    vi.runAllTimers()
    vi.useRealTimers()
    expect(document.title).toBe('Horizon')
    wrapper.unmount()
  })

  it('Shift + Print: without the Horizon name (the preview keeps it)', async () => {
    const wrapper = mount(ReportDialog, {
      props: { modelValue: true, analysisId: 3 },
      attachTo: document.body,
      global: { plugins: [vuetify, i18n] },
    })
    await settle()
    const preview = inBody('[data-testid="report-preview"]') as HTMLIFrameElement
    expect(preview.srcdoc).toContain('class="brand">Horizon<')
    inBody('[data-testid="report-print"]')!.dispatchEvent(
      new MouseEvent('click', { bubbles: true, shiftKey: true }),
    )
    await settle()
    const printed = vi.mocked(html.printDocument).mock.calls[0]![0]
    expect(printed).not.toContain('Horizon')
    expect(printed).toContain('EFMV-2026-0661')
    expect(preview.srcdoc).toContain('class="brand">Horizon<')
    wrapper.unmount()
  })

  it('the report’s language can change (the user’s at first); it names who created it', async () => {
    const wrapper = mount(ReportDialog, {
      props: { modelValue: true, analysisId: 3 },
      attachTo: document.body,
      global: { plugins: [vuetify, i18n] },
    })
    await settle()
    const preview = () => (inBody('[data-testid="report-preview"]') as HTMLIFrameElement).srcdoc
    expect(preview()).toContain('Análise de eFMV')
    expect(preview()).toContain('Bruno Reis')
    await pickOption('report-language', 'Español')
    expect(preview()).toContain('Análisis de eFMV')
    expect(preview()).toContain('36 Meses')
    expect(preview()).toContain('Nota: [EFMV-2026-0661].')
    // The interface stays in the user's language
    expect(document.body.textContent).toContain('Cenários')
    wrapper.unmount()
  })
})
