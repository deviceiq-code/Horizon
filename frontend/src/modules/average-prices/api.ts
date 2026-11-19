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
  /** Documents of the row (shared by all its versions) */
  documents_count: number
  /** The asset's photo (shared by all versions); changes when replaced */
  photo_id: number | null
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

/** Average of the versions not deleted (computed by the API). */
export interface VersionsAverage {
  count: number
  original_value: string
  /** Per term: average value and average of the versions' percentages; `count` versions have it */
  points: { term_months: number; value: string; percent: string; count: number }[]
}

export interface PriceHistory {
  /** Every version, newest first */
  versions: AveragePrice[]
  average: VersionsAverage | null
}

export function getAveragePriceHistory(id: number) {
  return api<PriceHistory>(`${BASE}${id}/history/`)
}

/** Values already used for a specification field of an asset class, most used first. */
export function getSpecSuggestions(assetClassId: number, key: string, search: string) {
  const query = new URLSearchParams({ asset_class: String(assetClassId), key, search })
  return api<string[]>(`${BASE}spec-suggestions/?${query}`)
}

export function createAveragePrice(data: AveragePriceInput) {
  return api<AveragePriceDetail>(BASE, { method: 'POST', body: JSON.stringify(data) })
}

/** Hides every version of the row (it leaves the list); they are kept as history. */
export function deleteAveragePrice(id: number) {
  return api<void>(`${BASE}${id}/history/`, { method: 'DELETE' })
}

/**
 * Erases one version for good. If it was the current one, the newest version left becomes
 * current; erasing the only version erases the row.
 */
export function deleteAveragePriceVersion(id: number) {
  return api<void>(`${BASE}${id}/`, { method: 'DELETE' })
}

/** Values, warnings and curve for what is being typed (nothing is saved). */
export function previewAveragePrice(data: { original_value: string; points: PricePointInput[] }) {
  return api<PreviewResult>(`${BASE}preview/`, { method: 'POST', body: JSON.stringify(data) })
}

// --- Documents (shared by every version of the row) --------------------------------------------

export interface PriceDocument {
  id: number
  /** Original file name */
  name: string
  /** Bytes */
  size: number
  content_type: string
  /** PDFs and images open in the browser; other files are downloaded */
  opens_inline: boolean
  uploaded_at: string
  uploaded_by_name: string | null
}

export function listPriceDocuments(rowId: number) {
  return api<PriceDocument[]>(`${BASE}${rowId}/documents/`)
}

/** Errors come as {"file": [...]} (type not accepted, too large…). */
export function uploadPriceDocument(rowId: number, file: File) {
  const body = new FormData()
  body.append('file', file)
  return api<PriceDocument>(`${BASE}${rowId}/documents/`, { method: 'POST', body })
}

export function deletePriceDocument(rowId: number, documentId: number) {
  return api<void>(`${BASE}${rowId}/documents/${documentId}/`, { method: 'DELETE' })
}

/** Link to the file (the session cookie authorizes it); `inline` opens PDFs/images in a tab. */
export function priceDocumentUrl(rowId: number, documentId: number, inline = false) {
  return `/api${BASE}${rowId}/documents/${documentId}/download/${inline ? '?inline=1' : ''}`
}

// --- Photo of the asset (one per row) -----------------------------------------------------------

/** Image URL; the photo id makes the browser fetch it again after a replacement. */
export function pricePhotoUrl(rowId: number, photoId: number) {
  return `/api${BASE}${rowId}/photo/?v=${photoId}`
}

/** Sets or replaces the photo. Errors come as {"file": [...]}. */
export function uploadPricePhoto(rowId: number, file: File) {
  const body = new FormData()
  body.append('file', file)
  return api<{ photo_id: number }>(`${BASE}${rowId}/photo/`, { method: 'POST', body })
}

export function deletePricePhoto(rowId: number) {
  return api<void>(`${BASE}${rowId}/photo/`, { method: 'DELETE' })
}
