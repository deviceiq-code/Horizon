import { mount } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { i18n, setLanguage } from '@/i18n'
import vuetify from '@/plugins/vuetify'
import { inBody, settle } from '@/test-utils'
import * as efmvApi from '../api'
import AnalysisScenariosPanel from '../AnalysisScenariosPanel.vue'

vi.mock('../api', () => ({ getEfmvAnalysis: vi.fn<typeof efmvApi.getEfmvAnalysis>() }))
const efmv = vi.mocked(efmvApi)

const scenario = (id: number, title: string, totals: Partial<efmvApi.ScenarioTotals>) =>
  ({
    id,
    name: '',
    title,
    term_months: 36,
    scope: '',
    items: [{ currency: 'BRL' }, { currency: 'BRL' }],
    has_expired: false,
    totals: {
      lo: '0.00',
      efmv_total: '0.00',
      efmv_percent: null,
      hw_percent: null,
      sw_percent: null,
      sv_percent: null,
      ...totals,
    },
  }) as unknown as efmvApi.Scenario

describe('AnalysisScenariosPanel', () => {
  beforeEach(() => setLanguage('en'))
  afterEach(() => {
    vi.clearAllMocks()
    document.body.innerHTML = ''
  })

  it("shows each scenario's LO, eFMV at EOL and HW / SW / SV shares", async () => {
    efmv.getEfmvAnalysis.mockResolvedValue({
      id: 3,
      scenarios: [
        scenario(1, '36 Months', {
          lo: '210000.00',
          efmv_total: '110000.00',
          efmv_percent: '52.38',
          hw_percent: '95.24',
          sw_percent: '0.00',
          sv_percent: '4.76',
        }),
        scenario(2, '60 Months - Desktops', {}),
      ],
    } as efmvApi.EfmvAnalysis)
    const wrapper = mount(AnalysisScenariosPanel, {
      props: { analysisId: 3 },
      attachTo: document.body,
      global: { plugins: [vuetify, i18n] },
    })
    await settle()
    expect(efmv.getEfmvAnalysis).toHaveBeenCalledWith(3)
    const rows = document.querySelectorAll('[data-testid="analysis-scenario"]')
    expect(rows).toHaveLength(2)
    expect(rows[0]!.textContent).toContain('36 Months')
    expect(inBody('[data-testid="scenario-lo"]')!.textContent).toMatch(/R\$\s?210,000\.00/)
    expect(inBody('[data-testid="scenario-efmv"]')!.textContent).toMatch(/52\.38%.*110,000\.00/)
    expect(inBody('[data-testid="scenario-hw"]')!.textContent).toContain('95.24%')
    expect(inBody('[data-testid="scenario-sv"]')!.textContent).toContain('4.76%')
    // The bar: a segment per share (hidden when 0)
    const segments = [...rows[0]!.querySelectorAll<HTMLElement>('.share-segment')]
    expect(segments.map((s) => s.style.width)).toEqual(['95.24%', '0%', '4.76%'])
    // A scenario without assets: dashes
    expect(rows[1]!.textContent).toContain('—')
    wrapper.unmount()
  })
})
