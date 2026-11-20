/**
 * eFMV analyses (Estimated Fair Market Value): for a customer and its account manager, one or
 * more scenarios (name, term, scope and assets from Average Prices with quantities). The API
 * computes every figure: per scenario the LO (Leasing Origination, total value of the assets),
 * the eFMV at the end of the lease (to come) and the HW/SW/SV shares.
 */
import { api, listQuery, type ListParams, type Paginated } from '@/api'
import type { AccountManagerRef } from '@/modules/account-managers/api'

export interface CustomerRef {
  id: number
  name: string
  trade_name: string
  tax_id: string
}

/** Figures of a scenario (decimal strings); percentages in 0–100 scale with 2 places. */
export interface ScenarioTotals {
  lo: string
  /** eFMV at the end of the lease, % of the LO — not computed yet */
  efmv_percent: string | null
  /** null while the scenario has no value */
  hw_percent: string | null
  sw_percent: string | null
  sv_percent: string | null
}

/** An asset of a scenario: the current version of an average price, and how many. */
export interface ScenarioItem {
  id: number | null
  quantity: number
  /** false: the average price was deleted (left out of the totals; removed when saving) */
  available: boolean
  /** Current version (null when deleted) */
  average_price: number | null
  asset_class?: { name: string; icon: string }
  manufacturer?: string
  model?: string
  sub_vertical?: string
  original_value?: string
  currency?: string
  /** Terms of its value curve (it stops at the last one) */
  terms?: number[]
  line_total: string | null
  /** The curve does not reach the scenario's term (left out of the totals; refused on save) */
  out_of_curve: boolean
}

export interface Scenario {
  id: number
  name: string
  term_months: number
  scope: string
  items: ScenarioItem[]
  totals: ScenarioTotals
}

export interface EfmvAnalysis {
  id: number
  /** EFMV-<year>-<number> */
  code: string
  account_manager: number
  account_manager_detail: AccountManagerRef
  customer: number
  customer_detail: CustomerRef
  scenarios: Scenario[]
  created_at: string
  created_by_name: string | null
  updated_at: string
}

export interface EfmvAnalysisRow {
  id: number
  code: string
  account_manager_detail: AccountManagerRef
  customer_detail: CustomerRef
  scenario_names: string[]
  created_at: string
  created_by_name: string | null
}

export interface ScenarioItemInput {
  /** Any version of the average price (its current version is used) */
  average_price: number
  quantity: number
}

export interface ScenarioInput {
  name: string
  term_months: number
  scope: string
  items: ScenarioItemInput[]
}

export interface EfmvAnalysisInput {
  account_manager: number
  customer: number
  /** At least one; they replace the analysis's scenarios */
  scenarios: ScenarioInput[]
}

export interface ScenarioPreview {
  items: ScenarioItem[]
  totals: ScenarioTotals
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

export function updateEfmvAnalysis(id: number, data: EfmvAnalysisInput) {
  return api<EfmvAnalysis>(`${BASE}${id}/`, { method: 'PUT', body: JSON.stringify(data) })
}

export function deleteEfmvAnalysis(id: number) {
  return api<void>(`${BASE}${id}/`, { method: 'DELETE' })
}

/** Figures of a scenario being edited (nothing is saved). */
export function previewScenario(data: { term_months: number; items: ScenarioItemInput[] }) {
  return api<ScenarioPreview>(`${BASE}scenario-preview/`, {
    method: 'POST',
    body: JSON.stringify(data),
  })
}
