import { describe, expect, it } from 'vitest'

import type { EfmvAnalysis, Scenario } from '../api'
import { disclaimerFor, extras, fillDisclaimer, reportHtml, type ReportFormat } from '../report'

const TOTALS = {
  lo: '1424150.49',
  efmv_total: '207500.00',
  efmv_percent: '14.57000',
  hw_percent: '100.00000',
  sw_percent: '0.00000',
  sv_percent: '0.00000',
  hw_total: '1424150.49',
  sw_total: '0.00',
  sv_total: '0.00',
}

const scenario = (id: number, title: string, items: Scenario['items'] = []): Scenario =>
  ({
    id,
    name: '',
    title,
    term_months: 36,
    scope: '',
    scope_suggestion: 'Dell Laptops and Monitors',
    items,
    totals: TOTALS,
    has_expired: false,
  }) as Scenario

const LAPTOP = {
  id: 1,
  kind: 'hw',
  quantity: 2,
  unit_value: '5000.00',
  net_unit_value: '5000.00',
  line_total: '10000.00',
  efmv_value: '1000.00',
  efmv_percent: '20.00000',
  weight_percent: '50.00000',
  manufacturer: 'Dell',
  model: 'Latitude 5440',
  asset_class: { name: 'Laptops', icon: 'mdi-laptop' },
  specs: [],
  service: {
    name: 'Warranty <3y>',
    mode: 'add',
    value: '300.00',
    line_total: '600.00',
    weight_percent: '3.00000',
    too_high: false,
  },
  software: null,
  available: true,
  average_price: 9,
  expired: false,
  out_of_curve: false,
} as unknown as Scenario['items'][number]

const ANALYSIS = {
  id: 3,
  code: 'EFMV-2026-0661',
  external_reference: 'OPP-00661',
  account_manager_detail: { id: 1, full_name: 'Ana Lima' },
  customer_detail: { id: 2, name: 'IHM Engenharia Ltda', trade_name: 'Stefanini/IHM', tax_id: '' },
  vertical_label: 'IT',
  created_by_name: 'Bruno Reis',
  created_at: '2026-11-20T10:00:00Z',
  scenarios: [scenario(10, '36 Months - Dell'), scenario(11, '48 Months', [LAPTOP])],
} as unknown as EfmvAnalysis

const F: ReportFormat = {
  t: (key, values) => (values ? `${key}${JSON.stringify(values)}` : key),
  money: (value) => `R$ ${value}`,
  percent: (value) => `${Number(value).toFixed(2)}%`,
  date: () => '27/11/2026',
  specs: () => '',
  title: (scenario) => scenario.title,
}

describe('eFMV report', () => {
  it('fills the disclaimer variables; English when a language has none', () => {
    expect(
      fillDisclaimer('Put [{code}] — {customer}, {unknown}', {
        code: 'EFMV-1',
        external_reference: 'OPP-1',
        customer: 'Acme',
        account_manager: 'Ana',
        date: 'today',
      }),
    ).toBe('Put [EFMV-1] — Acme, {unknown}')
    expect(disclaimerFor({ en: 'Note', 'pt-br': ' ' }, 'pt-br')).toBe('Note')
    expect(disclaimerFor({ en: 'Note', es: 'Nota' }, 'es')).toBe('Nota')
  })

  it('only the scenarios chosen, with their figures, services and the disclaimer', () => {
    const html = reportHtml(
      ANALYSIS,
      {
        scenarioIds: [10],
        assets: false,
        disclaimer: 'Add [{code}] to each asset ({external_reference}).',
        printedAt: '2026-11-27T10:00:00Z',
      },
      F,
    )
    expect(html).toContain('36 Months - Dell')
    expect(html).not.toContain('48 Months')
    expect(html).toContain('Stefanini/IHM')
    // Who created it
    expect(html).toContain('Bruno Reis')
    expect(html).toContain('R$ 1424150.49')
    expect(html).toContain('14.57%')
    // The scope: written from the assets when not typed
    expect(html).toContain('Dell Laptops and Monitors')
    expect(html).toContain('efmv.report.noServices')
    expect(html).toContain('Add [EFMV-2026-0661] to each asset (OPP-00661).')
    expect(html).not.toContain('efmv.report.assets')
  })

  it('services attached to hardware are listed (escaped), and the assets on request', () => {
    expect(extras(ANALYSIS.scenarios[1]!, 'sv', 'Service')).toEqual([
      {
        name: 'Warranty <3y>',
        of: 'Dell Latitude 5440',
        quantity: 2,
        value: '300.00',
        total: '600.00',
        deducted: false,
      },
    ])
    const html = reportHtml(
      ANALYSIS,
      { scenarioIds: [11], assets: true, disclaimer: '', printedAt: '2026-11-27T10:00:00Z' },
      F,
    )
    expect(html).toContain('Warranty &#60;3y&#62;')
    expect(html).toContain('efmv.report.assets')
    expect(html).toContain('Latitude 5440')
    expect(html).not.toContain('class="disclaimer"')
  })

  it("follows the user's theme: colors and font", () => {
    const html = reportHtml(
      ANALYSIS,
      {
        scenarioIds: [10],
        assets: false,
        disclaimer: '',
        printedAt: '2026-11-27T10:00:00Z',
        style: {
          primary: '#2052E4',
          accent: '#FF2063',
          text: '#1C1C1C',
          tint: '#E9F2FF',
          fontFamily: "'Poppins', sans-serif",
          fontFaces: "@font-face { font-family: 'Poppins'; src: url(/assets/poppins.woff2); }",
        },
      },
      F,
    )
    expect(html).toContain("font-family: 'Poppins', sans-serif")
    expect(html).toContain('url(/assets/poppins.woff2)')
    expect(html).toContain('border-bottom: 2px solid #FF2063')
    expect(html).toContain('color: #2052E4')
  })
})
