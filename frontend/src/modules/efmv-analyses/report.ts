/**
 * The printed report of an eFMV analysis: the scenarios chosen, each with its figures (LO, eFMV
 * at the end of the term, HW / SW / SV shares), its software and services and — optionally — its
 * list of assets; and, at the end, the disclaimer of the Pricing settings in the user's
 * language. Built as a whole HTML document from what the API returned (nothing is calculated
 * here): the dialog previews it in a frame and prints that same frame. Reports are not stored —
 * they are made again whenever needed.
 */
import { escapeHtml } from '@/utils/html'
import type { EfmvAnalysis, ItemService, Scenario, ScenarioItem } from './api'

/** What a disclaimer may use: filled in when the report is made */
export const DISCLAIMER_VARIABLES = [
  'code',
  'external_reference',
  'customer',
  'account_manager',
  'date',
] as const
export type DisclaimerVariable = (typeof DISCLAIMER_VARIABLES)[number]
export const MAX_DISCLAIMER = 4000

/** {code} → "EFMV-2026-0012"…; unknown names are left as typed. */
export function fillDisclaimer(text: string, values: Record<DisclaimerVariable, string>): string {
  return text.replace(/\{(\w+)\}/g, (whole, name: string) =>
    name in values ? values[name as DisclaimerVariable] : whole,
  )
}

/** The disclaimer in a language, or the English one when that language has none */
export function disclaimerFor(texts: Record<string, string>, language: string): string {
  return (texts[language] ?? '').trim() || (texts.en ?? '').trim()
}

export interface ReportOptions {
  scenarioIds: number[]
  /** Each scenario's list of assets too */
  assets: boolean
  /** The disclaimer as written for the user's language (variables not filled in yet) */
  disclaimer: string
  /** When it is printed (ISO) */
  printedAt: string
  /** Without the "Horizon" name (while the project is private: Shift + Print) */
  unbranded?: boolean
  /** The user's theme (default: Emerald Slate's colors, Arial) */
  style?: ReportStyle
}

/** The report's look, from the user's color theme (its light version: paper is white). */
export interface ReportStyle {
  /** Section titles and the figures' frame */
  primary: string
  /** The rule under the header and the Horizon name (the theme's brand color) */
  accent: string
  /** Body text */
  text: string
  /** A soft background for the main figures */
  tint: string
  /** CSS font-family */
  fontFamily: string
  /** The font's @font-face rules (the frame does not see the page's fonts) */
  fontFaces: string
}

export const DEFAULT_REPORT_STYLE: ReportStyle = {
  primary: '#00926F',
  accent: '#00926F',
  text: '#1C252E',
  tint: '#F4F6F8',
  fontFamily: 'Arial, Helvetica, sans-serif',
  fontFaces: '',
}

/** How the report writes texts, money, percentages, dates and specifications. */
export interface ReportFormat {
  t: (key: string, values?: Record<string, unknown>) => string
  money: (value: string, currency: string) => string
  percent: (value: string) => string
  date: (iso: string) => string
  specs: (item: ScenarioItem) => string
  /** A scenario's official name in the report's language ("36 Months - Desktops") */
  title: (scenario: Scenario) => string
}

const currencyOf = (scenario: Scenario) => scenario.items.find((i) => i.currency)?.currency ?? 'BRL'

const customerName = (analysis: EfmvAnalysis) =>
  analysis.customer_detail.trade_name || analysis.customer_detail.name

/** One software or service of a scenario, as listed in the report */
interface Extra {
  name: string
  /** Attached: the hardware it goes with */
  of?: string
  quantity: number
  value: string
  total: string
  deducted: boolean
}

function hardwareName(item: ScenarioItem): string {
  return [item.manufacturer, item.model].filter(Boolean).join(' ')
}

/** The software (sw) or services (sv) of a scenario: of their own and attached to hardware. */
export function extras(scenario: Scenario, kind: 'sw' | 'sv', defaultName: string): Extra[] {
  const key = kind === 'sw' ? 'software' : 'service'
  const list: Extra[] = []
  for (const item of scenario.items) {
    if (item.kind === kind) {
      list.push({
        name: item.description || defaultName,
        quantity: item.quantity,
        value: item.unit_value ?? '0',
        total: item.line_total ?? '0',
        deducted: false,
      })
    }
    const attached: ItemService | null | undefined = item[key]
    if ((!item.kind || item.kind === 'hw') && attached) {
      list.push({
        name: attached.name || defaultName,
        of: hardwareName(item),
        quantity: item.quantity,
        value: attached.value,
        total: attached.line_total,
        deducted: attached.mode === 'deduct',
      })
    }
  }
  return list
}

function extrasBlock(
  scenario: Scenario,
  kind: 'sw' | 'sv',
  f: ReportFormat,
  currency: string,
): string {
  const t = f.t
  const list = extras(
    scenario,
    kind,
    t(kind === 'sw' ? 'efmv.software.defaultName' : 'efmv.service.defaultName'),
  )
  const title = t(kind === 'sw' ? 'efmv.report.software' : 'efmv.report.services')
  const items = list.length
    ? list
        .map(
          (e) =>
            `<li><strong>${escapeHtml(e.name)}</strong>${
              e.of ? ` <span class="muted">(${escapeHtml(e.of)})</span>` : ''
            } — ${e.quantity} × ${escapeHtml(f.money(e.value, currency))} = ${escapeHtml(
              f.money(e.total, currency),
            )}${e.deducted ? ` <span class="muted">· ${escapeHtml(t('efmv.report.deducted'))}</span>` : ''}</li>`,
        )
        .join('')
    : `<li class="muted">${escapeHtml(t(kind === 'sw' ? 'efmv.report.noSoftware' : 'efmv.report.noServices'))}</li>`
  return `<div class="block"><h3>${escapeHtml(title)}</h3><ul>${items}</ul></div>`
}

function assetsTable(scenario: Scenario, f: ReportFormat, currency: string): string {
  const t = f.t
  const money = (v: string | null | undefined) => (v ? escapeHtml(f.money(v, currency)) : '—')
  const pct = (v: string | null | undefined) => (v ? escapeHtml(f.percent(v)) : '—')
  const rows = scenario.items
    .map((item, index) => {
      const standalone = !!item.kind && item.kind !== 'hw'
      const name = standalone
        ? escapeHtml(
            item.description ||
              t(item.kind === 'sw' ? 'efmv.software.defaultName' : 'efmv.service.defaultName'),
          )
        : `<strong>${escapeHtml(hardwareName(item))}</strong>${
            item.asset_class || f.specs(item)
              ? `<div class="muted">${escapeHtml(
                  [item.asset_class?.name, f.specs(item)].filter(Boolean).join(' · '),
                )}</div>`
              : ''
          }`
      const kind = t(`efmv.kinds.${item.kind ?? 'hw'}Short`)
      const main = `<tr><td class="num">${index + 1}</td><td>${kind}</td><td class="num">${item.quantity}</td><td>${name}</td><td class="num">${money(item.net_unit_value ?? item.unit_value)}</td><td class="num">${money(item.efmv_value)}<div class="muted">${pct(item.efmv_percent)}</div></td><td class="num">${money(item.line_total)}</td><td class="num">${pct(item.weight_percent)}</td></tr>`
      const attached = (['software', 'service'] as const)
        .filter((key) => item[key])
        .map((key) => {
          const a = item[key]!
          const label = a.name || t(`efmv.${key}.defaultName`)
          const efmv = key === 'software' ? item.software!.efmv_value : '0'
          return `<tr class="sub"><td></td><td>${t(`efmv.kinds.${key === 'software' ? 'sw' : 'sv'}Short`)}</td><td></td><td>↳ ${escapeHtml(label)}${
            a.mode === 'deduct'
              ? ` <span class="muted">· ${escapeHtml(t('efmv.report.deducted'))}</span>`
              : ''
          }</td><td class="num">${money(a.value)}</td><td class="num">${money(efmv)}</td><td class="num">${money(a.line_total)}</td><td class="num">${pct(a.weight_percent)}</td></tr>`
        })
        .join('')
      return main + attached
    })
    .join('')
  const head = [
    '#',
    t('efmv.report.kind'),
    t('efmv.item.quantity'),
    t('efmv.item.asset'),
    t('efmv.item.unitValue'),
    t('efmv.item.efmvValue'),
    t('efmv.item.total'),
    t('efmv.report.weight'),
  ]
    .map((h, i) => `<th${i === 0 || i === 2 || i >= 4 ? ' class="num"' : ''}>${escapeHtml(h)}</th>`)
    .join('')
  return `<div class="block"><h3>${escapeHtml(t('efmv.report.assets'))}</h3><table class="assets"><thead><tr>${head}</tr></thead><tbody>${rows}</tbody></table></div>`
}

function scenarioSection(scenario: Scenario, options: ReportOptions, f: ReportFormat): string {
  const t = f.t
  const currency = currencyOf(scenario)
  const totals = scenario.totals
  const scope = scenario.scope || scenario.scope_suggestion || ''
  const share = (key: 'hw' | 'sw' | 'sv') =>
    `<td><div class="label">${escapeHtml(t(`efmv.totals.${key}`))}</div><div class="value">${
      totals[`${key}_percent`] ? escapeHtml(f.percent(totals[`${key}_percent`]!)) : '—'
    }</div><div class="muted">${escapeHtml(f.money(totals[`${key}_total`], currency))}</div></td>`
  const figures = `<table class="figures"><tr>
<td class="main"><div class="label">${escapeHtml(t('efmv.totals.lo'))}</div><div class="value">${escapeHtml(f.money(totals.lo, currency))}</div></td>
<td class="main"><div class="label">${escapeHtml(t('efmv.totals.efmv'))}</div><div class="value">${
    totals.efmv_percent ? escapeHtml(f.percent(totals.efmv_percent)) : '—'
  }</div><div class="muted">${escapeHtml(f.money(totals.efmv_total, currency))}</div></td>
${share('hw')}${share('sw')}${share('sv')}</tr></table>`
  return `<section class="scenario">
<h2>${escapeHtml(t('efmv.report.scenario'))} ${escapeHtml(f.title(scenario))}</h2>
${scope ? `<p class="scope">${escapeHtml(scope)}</p>` : ''}
${figures}
${extrasBlock(scenario, 'sv', f, currency)}
${extrasBlock(scenario, 'sw', f, currency)}
${options.assets ? assetsTable(scenario, f, currency) : ''}
</section>`
}

/**
 * The name the browser suggests when the report is saved as PDF (it takes the document's
 * title): "<code> - <customer> - <vertical>". "/" cannot be in a file name, so the vertical's
 * sub-vertical is separated the same way ("Industry / Yellow Line" → "Industry - Yellow Line");
 * the other characters file systems refuse are left out.
 */
export function reportFileName(
  analysis: Pick<EfmvAnalysis, 'code' | 'customer_detail' | 'vertical_label'>,
): string {
  const customer = analysis.customer_detail.trade_name || analysis.customer_detail.name
  return [analysis.code, customer, analysis.vertical_label]
    .filter((part) => part && part.trim())
    .join(' - ')
    .replace(/\s*\/\s*/g, ' - ')
    .replace(/[\\:*?"<>|]/g, '')
    .replace(/\s+/g, ' ')
    .trim()
}

export function reportHtml(
  analysis: EfmvAnalysis,
  options: ReportOptions,
  f: ReportFormat,
): string {
  const t = f.t
  const style = options.style ?? DEFAULT_REPORT_STYLE
  const chosen = analysis.scenarios.filter((s) => options.scenarioIds.includes(s.id))
  const customer = customerName(analysis)
  const printed = f.date(options.printedAt)
  const disclaimer = fillDisclaimer(options.disclaimer, {
    code: analysis.code,
    external_reference: analysis.external_reference ?? '',
    customer,
    account_manager: analysis.account_manager_detail.full_name,
    date: printed,
  })
  const meta = [
    [
      t('efmv.report.customer'),
      customer,
      analysis.customer_detail.trade_name ? analysis.customer_detail.name : '',
    ],
    [t('efmv.report.analysis'), analysis.code, analysis.external_reference ?? ''],
    [t('efmv.report.accountManager'), analysis.account_manager_detail.full_name, ''],
    [t('efmv.report.vertical'), analysis.vertical_label ?? '—', ''],
    [t('efmv.report.createdBy'), analysis.created_by_name ?? '—', f.date(analysis.created_at)],
    [
      t('efmv.report.changedBy'),
      analysis.updated_by_name ?? '—',
      analysis.updated_at ? f.date(analysis.updated_at) : '',
    ],
    [t('efmv.report.printedOn'), printed, ''],
  ]
    .map(
      ([label, value, detail]) =>
        `<div class="meta-item"><div class="label">${escapeHtml(label!)}</div><div class="value">${escapeHtml(value!)}</div>${
          detail ? `<div class="muted">${escapeHtml(detail)}</div>` : ''
        }</div>`,
    )
    .join('')
  const title = `${t('efmv.report.title')} ${analysis.code}`
  return `<!doctype html>
<html><head><meta charset="utf-8"><title>${escapeHtml(reportFileName(analysis))}</title>
<style>
${style.fontFaces}
  @page { size: A4; margin: 15mm; }
  * { box-sizing: border-box; }
  body { margin: 0; font-family: ${style.fontFamily}; font-size: 10pt; color: ${style.text}; }
  .sheet { padding: 8mm; }
  @media print { .sheet { padding: 0; } }
  header { display: flex; justify-content: space-between; align-items: flex-end; border-bottom: 2px solid ${style.accent}; padding-bottom: 4mm; margin-bottom: 5mm; }
  .brand { font-size: 16pt; font-weight: bold; color: ${style.accent}; }
  .doc-title { font-size: 13pt; font-weight: bold; }
  .meta { display: grid; grid-template-columns: repeat(3, 1fr); gap: 3mm 6mm; margin-bottom: 6mm; }
  .label { font-size: 8pt; color: #637381; text-transform: uppercase; letter-spacing: 0.04em; }
  .value { font-size: 10.5pt; font-weight: bold; }
  .muted { color: #637381; font-size: 8.5pt; font-weight: normal; }
  .scenario { page-break-inside: avoid; break-inside: avoid; border: 1px solid #dfe3e8; border-radius: 3mm; padding: 4mm 5mm; margin-bottom: 5mm; }
  h2 { font-size: 12pt; margin: 0 0 2mm; }
  h3 { font-size: 9.5pt; margin: 4mm 0 1.5mm; text-transform: uppercase; letter-spacing: 0.04em; color: ${style.primary}; }
  .scope { margin: 0 0 3mm; }
  table { border-collapse: collapse; width: 100%; }
  .figures td { border: 1px solid #dfe3e8; padding: 2mm 3mm; vertical-align: top; width: 20%; }
  .figures td.main { background: ${style.tint}; }
  .scenario h2 { color: ${style.text}; border-left: 3px solid ${style.primary}; padding-left: 2.5mm; }
  .figures td.main .value { font-size: 12pt; }
  ul { margin: 0; padding-left: 5mm; }
  li { margin: 0.8mm 0; }
  .assets th, .assets td { border-bottom: 1px solid #dfe3e8; padding: 1.5mm 1.5mm; text-align: left; vertical-align: top; }
  .assets th { font-size: 8pt; color: #637381; text-transform: uppercase; }
  .assets .num { text-align: right; white-space: nowrap; }
  .assets tr.sub td { color: #454f5b; font-size: 9pt; }
  .disclaimer { white-space: pre-line; border-top: 1px solid #dfe3e8; padding-top: 4mm; margin-top: 6mm; font-size: 9pt; }
</style></head><body><div class="sheet">
<header><div>${options.unbranded ? '' : '<div class="brand">Horizon</div>'}<div class="doc-title">${escapeHtml(title)}</div></div><div class="muted">${escapeHtml(t('efmv.report.subtitle'))}</div></header>
<div class="meta">${meta}</div>
${chosen.map((s) => scenarioSection(s, options, f)).join('\n')}
${disclaimer ? `<div class="disclaimer">${escapeHtml(disclaimer)}</div>` : ''}
</div></body></html>`
}
