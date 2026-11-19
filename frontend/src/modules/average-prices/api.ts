import { api, listQuery, type ListParams, type Paginated } from '@/api'
import type { SpecField } from '@/modules/catalogs/asset-classes/api'

export type AnchorMode = 'value' | 'percent'

export interface PricePoint {
  term_months: number
  /** How it was entered: fixed value or % of the original value */
  mode: AnchorMode
  /** As entered (money or percentage), decimal string with 4 places */
  amount: string
  /** Resulting money value (computed by the API) */
  value: string
  /** `value` as % of the original value (computed by the API) */
  percent: string
}

/** A specification as stored with the row: the template field plus the value given. */
export type SpecValue = SpecField & { value: string }

/** An average price row. Rows are never edited: a change is a new version (`supersedes`). */
export interface AveragePrice {
  id: number
  vertical: { id: number; name: string }
  sub_vertical: { id: number; label: string }
  asset_class: { id: number; name: string; icon: string }
  manufacturer: { id: number; name: string }
  model: string
  description: string
  specs: SpecValue[]
  currency: string
  original_value: string
  points: PricePoint[]
  /** Terms worth more than the point before them (a warning, not an error) */
  increasing_terms: number[]
  is_current: boolean
  supersedes: number | null
  created_at: string
  created_by_name: string | null
  deleted_at: string | null
}

export interface CurvePoint {
  month: number
  value: string
  percent: string
  /** Entered by the user (or month 0), not interpolated */
  is_anchor: boolean
}

export interface AveragePriceDetail extends AveragePrice {
  /** Value of every month from 0 to the last term (computed by the API) */
  curve: CurvePoint[]
}

export interface PricePointInput {
  term_months: number
  mode: AnchorMode
  /** Canonical decimal string */
  amount: string
}

export interface AveragePriceInput {
  asset_class: number
  manufacturer: number
  model: string
  description: string
  /** Template field key → value */
  specs: Record<string, string>
  currency: string
  original_value: string
  points: PricePointInput[]
  /** Set when creating a new version of an existing row */
  supersedes?: number | null
}

export interface PreviewResult {
  points: { term_months: number; value: string; percent: string }[]
  increasing_terms: number[]
  curve: CurvePoint[]
}

const BASE = '/average-prices/'

export function listAveragePrices(params: ListParams) {
  return api<Paginated<AveragePrice>>(BASE + listQuery(params))
}

export function getAveragePrice(id: number) {
  return api<AveragePriceDetail>(`${BASE}${id}/`)
}

export function getAveragePriceHistory(id: number) {
  return api<AveragePrice[]>(`${BASE}${id}/history/`)
}

export function createAveragePrice(data: AveragePriceInput) {
  return api<AveragePriceDetail>(BASE, { method: 'POST', body: JSON.stringify(data) })
}

/** Hides the row; it is kept as history. */
export function deleteAveragePrice(id: number) {
  return api<void>(`${BASE}${id}/`, { method: 'DELETE' })
}

/** Values, warnings and curve for what is being typed (nothing is saved). */
export function previewAveragePrice(data: { original_value: string; points: PricePointInput[] }) {
  return api<PreviewResult>(`${BASE}preview/`, { method: 'POST', body: JSON.stringify(data) })
}
