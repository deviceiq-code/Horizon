/**
 * eFMV analyses (Estimated Fair Market Value): for a customer and its account manager, one or
 * more scenarios (name, term, scope and assets from Average Prices with quantities). The API
 * computes every figure: per scenario the LO (Leasing Origination, total value of the assets),
 * the eFMV at the end of the lease (the assets' eFMV weighted over the LO; per asset, the value
 * of one unit at the end of the term — the average price's curve at the term or typed by the
 * analyst) and the HW/SW/SV shares.
 */
import { api, listQuery, type ListParams, type Paginated } from '@/api'
import type { AccountManagerRef } from '@/modules/account-managers/api'
import type { SpecValue } from '@/modules/average-prices/api'

export interface CustomerRef {
  id: number
  name: string
  trade_name: string
  tax_id: string
}

/** Figures of a scenario (decimal strings); percentages in 0–100 scale with 2 places. */
export interface ScenarioTotals {
  lo: string
  /** Σ quantity × eFMV value: what the assets are worth at the end of the term */
  efmv_total: string
  /** eFMV at the end of the lease weighted over the LO (efmv_total / LO, %); null without LO */
  efmv_percent: string | null
  /** null while the scenario has no value */
  hw_percent: string | null
  sw_percent: string | null
  sv_percent: string | null
  /** The same shares in money */
  hw_total: string
  sw_total: string
  sv_total: string
}

/** How a typed value compares with Average Prices (limits set in the Pricing control panel). */
export type PricePosition = 'below' | 'slightly_below' | 'compatible' | 'slightly_above' | 'above'

/**
 * An asset of a scenario: the current version of an average price, how many and the value
 * typed by the analyst (Average Prices only position it).
 */
export interface ScenarioItem {
  id: number | null
  /** Hardware (an average price), or software / a service of its own (absent: hardware) */
  kind?: ItemKind
  /** Software / service of its own: what it is ("": "Software" / "Service") */
  description?: string
  quantity: number
  /** The value that counts: typed by the analyst or, when not typed, the average price's */
  unit_value: string | null
  /** The asset's own value: without its service when the service was deducted from it */
  net_unit_value?: string | null
  /** Its service (SV) attached: eFMV 0; per unit, the item's quantity */
  service?: ItemService | null
  /** Its software (SW) attached: per unit, the item's quantity; with its eFMV */
  software?: (ItemService & { efmv_value: string | null; efmv_percent: string | null }) | null
  /** Not typed: the average price's value counts (stored with the analysis when saved) */
  value_from_price?: boolean
  /** quantity × unit value; null without a value */
  line_total: string | null
  /** One unit at the end of the term: typed, or the curve's value at the term (null beyond it) */
  efmv_value?: string | null
  /** The average price's curve at the scenario's term (the placeholder); null beyond the curve */
  curve_value?: string | null
  /** Not typed: the curve's value counts (it follows the term and the price's current version) */
  efmv_from_curve?: boolean
  /** The eFMV as a percentage of the unit value (2 places) */
  efmv_percent?: string | null
  /** Share of the scenario's LO (%, 2 places); null when left out of the totals */
  weight_percent?: string | null
  /** false: the average price was deleted (left out of the totals; removed when saving) */
  available: boolean
  /** Current version (null when deleted) */
  average_price: number | null
  asset_class?: { name: string; icon: string }
  manufacturer?: string
  model?: string
  /** Template fields with their values (as stored with the average price) */
  specs?: SpecValue[]
  sub_vertical?: string
  original_value?: string
  currency?: string
  /** Terms of its value curve (it stops at the last one) */
  terms?: number[]
  /** Date of the current version of the average price, and until when it is current */
  priced_on?: string
  valid_until?: string
  /** Older than the validity set in the control panel: the analysis may be out of date */
  expired: boolean
  /** Typed value against the average price's value, % (negative = below); null without a value */
  variation_percent?: string | null
  position?: PricePosition | null
  /** The curve does not reach the scenario's term (left out of the totals; refused on save) */
  out_of_curve: boolean
  /** Not of the scenario's vertical / sub-vertical (left out of the totals; refused on save) */
  out_of_scope?: boolean
}

export interface ItemService {
  name: string
  mode: 'add' | 'deduct'
  /** Per unit (resolved when typed as a percentage) */
  value: string
  line_total: string
  /** Share of the scenario's LO */
  weight_percent: string | null
  /** Deducted, it would leave nothing of the asset (refused on save) */
  too_high: boolean
}

export interface Scenario {
  id: number
  /** As given by the analyst; may be empty */
  name: string
  /** Official name: term + name ("36 Months - Desktops", "60 Months") */
  title: string
  term_months: number
  scope: string
  items: ScenarioItem[]
  totals: ScenarioTotals
  /** Some average price used is past its validity */
  has_expired: boolean
  /** Smart Tools: the scope written from its assets (the user's language and threshold) */
  scope_suggestion: string
}

export interface EfmvAnalysis {
  id: number
  /** EFMV-<year>-<number> */
  code: string
  account_manager: number
  account_manager_detail: AccountManagerRef
  customer: number
  customer_detail: CustomerRef
  /** The assets the scenarios admit: the vertical's, or only the sub-vertical's when set */
  vertical: number | null
  sub_vertical: number | null
  /** "Industry" or "Industry / Yellow line" */
  vertical_label: string | null
  /** Not a premise: they can change after creation */
  keywords: string[]
  /** Where it comes from elsewhere, e.g. the opportunity's number in a CRM (not a premise) */
  external_reference: string
  scenarios: Scenario[]
  /** Some average price used is past its validity: the analysis may be out of date */
  is_outdated: boolean
  created_at: string
  created_by_name: string | null
  updated_at: string
  updated_by_name: string | null
}

export interface EfmvAnalysisRow {
  id: number
  code: string
  /** E.g. the opportunity's number in a CRM */
  external_reference: string
  account_manager_detail: AccountManagerRef
  customer_detail: CustomerRef
  /** The scenarios' official names (term + name) */
  scenario_names: string[]
  created_at: string
  created_by_name: string | null
  /** When and by whom it was saved last (the list's default order: latest first) */
  updated_at: string
  updated_by_name: string | null
}

/** Hardware (an average price), software or a service */
export type ItemKind = 'hw' | 'sw' | 'sv'

export interface ScenarioItemInput {
  /** Absent: hardware */
  kind?: ItemKind
  /** Hardware: any version of the average price (its current version is used) */
  average_price?: number | null
  /** Software / service of its own: what it is (empty: "Software" / "Service") */
  description?: string
  quantity: number
  /** Canonical decimal string; null = not typed (the average price's value counts) */
  unit_value: string | null
  /** Canonical decimal string; null = not typed (the curve's value at the term counts) */
  efmv_value: string | null
  /** Or typed as a percentage of the unit value ("25" = 25%); the API turns it into a value */
  efmv_percent?: string
  /** Hardware: its service attached — a value per unit or a percentage of the asset's value */
  service?: { name: string; mode: 'add' | 'deduct'; value?: string; percent?: string }
  /** Hardware: its software attached — also its eFMV (value or % of its own value; empty: 0) */
  software?: {
    name: string
    mode: 'add' | 'deduct'
    value?: string
    percent?: string
    efmv_value?: string | null
    efmv_percent?: string
  }
}

export interface ScenarioInput {
  name: string
  term_months: number
  scope: string
  items: ScenarioItemInput[]
}

/** A new analysis (the wizard): its premises — fixed afterwards — and its first scenarios. */
export interface EfmvAnalysisInput {
  account_manager: number
  customer: number
  vertical: number
  sub_vertical: number | null
  keywords?: string[]
  external_reference?: string
  /** At least one */
  scenarios: ScenarioInput[]
}

/** What the wizard shows about an account manager. */
export interface AccountManagerSummary {
  id: number
  full_name: string
  email: string
  job_title: string
  photo_version: string | null
  /** Business verticals of their profile: the ones their analyses can be in */
  verticals: { id: number; name: string }[]
  analyses_count: number
  /** Their 5 verticals with most analyses */
  top_verticals: { id: number; name: string; analyses: number }[]
  /** Active customers they are the primary account manager of */
  primary_customers_count: number
}

export interface ScenarioPreview {
  items: ScenarioItem[]
  totals: ScenarioTotals
  has_expired: boolean
  /** Smart Tools: the scope written from the assets */
  scope_suggestion?: string
}

const BASE = '/efmv-analyses/'

/** ?search= (code, customer, account manager, scenario), ordering: code, created_at… */
export function listEfmvAnalyses(params: ListParams) {
  return api<Paginated<EfmvAnalysisRow>>(BASE + listQuery(params))
}

export function getEfmvAnalysis(id: number) {
  return api<EfmvAnalysis>(`${BASE}${id}/`)
}

/**
 * Validation errors are nested by position:
 * {"scenarios": {"0": {"name": [...], "items": {"1": {"average_price": [...]}}}}, "customer": [...]}
 */
export function createEfmvAnalysis(data: EfmvAnalysisInput) {
  return api<EfmvAnalysis>(BASE, { method: 'POST', body: JSON.stringify(data) })
}

/** The scenarios replace the analysis's (the premises do not change). */
export function updateEfmvAnalysis(
  id: number,
  data: { scenarios?: ScenarioInput[]; keywords?: string[]; external_reference?: string },
) {
  return api<EfmvAnalysis>(`${BASE}${id}/`, { method: 'PATCH', body: JSON.stringify(data) })
}

export function getAccountManagerSummary(accountManager: number) {
  return api<AccountManagerSummary>(
    `${BASE}account-manager-summary/?account_manager=${accountManager}`,
  )
}

export function deleteEfmvAnalysis(id: number) {
  return api<void>(`${BASE}${id}/`, { method: 'DELETE' })
}

/** Figures of a scenario being edited (nothing is saved). */
export function previewScenario(data: {
  term_months: number
  vertical: number | null
  sub_vertical: number | null
  items: ScenarioItemInput[]
}) {
  return api<ScenarioPreview>(`${BASE}scenario-preview/`, {
    method: 'POST',
    body: JSON.stringify(data),
  })
}
