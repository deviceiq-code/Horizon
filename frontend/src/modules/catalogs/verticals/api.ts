import { api, listQuery, type ListParams, type Paginated } from '@/api'
import type { AccountManagerRef } from '@/modules/account-managers/api'

export type Risk = 'low' | 'medium' | 'high'

export const RISKS: readonly Risk[] = ['low', 'medium', 'high']

export interface SubVertical {
  /** Absent for a sub-vertical that is not saved yet */
  id?: number
  /** Empty for the general sub-vertical (shown translated as "General") */
  name: string
  is_general: boolean
  risk: Risk
  /** Months, ascending */
  allowed_terms: number[]
  /** Months; one of allowed_terms (null only while editing) */
  recommended_term: number | null
}

export interface Vertical {
  id: number
  name: string
  /**
   * Account managers who work in this vertical, sorted by name. Read-only: they are assigned
   * on the account manager (AccountManager.verticals).
   */
  account_managers_detail: AccountManagerRef[]
  is_enabled: boolean
  notes: string
  /** General first, then by name */
  sub_verticals: SubVertical[]
  created_at: string
  updated_at: string
}

/** Sending sub_verticals replaces the whole list (it must include the general one). */
export type VerticalInput = Pick<Vertical, 'name' | 'is_enabled' | 'notes' | 'sub_verticals'>

/** Minimal reference to a vertical, as other modules display it. */
export type VerticalRef = Pick<Vertical, 'id' | 'name' | 'is_enabled'>

/** A sub-vertical as offered by pickers (/api/catalogs/sub-verticals/). */
export interface SubVerticalOption {
  id: number
  /** Translated "General" for the general sub-vertical */
  name: string
  is_general: boolean
  /** "Industry / Yellow line" */
  label: string
  vertical: VerticalRef
  /** Terms (months) prices must be given for, and the recommended one */
  allowed_terms: number[]
  recommended_term: number
}

/** Sub-verticals of every vertical, ordered by vertical (General first). */
export function listSubVerticals(params: ListParams) {
  return api<Paginated<SubVerticalOption>>('/catalogs/sub-verticals/' + listQuery(params))
}

/** Initial values for the general sub-vertical of a new vertical (defined by the backend). */
export interface SubVerticalDefaults {
  risk: Risk
  allowed_terms: number[]
  recommended_term: number
  /** Longest term accepted, in months */
  max_term_months: number
}

/**
 * Validation errors for sub_verticals: a message for the whole list, or field errors per
 * failing item keyed by its position ({"1": {"name": ["..."]}}).
 */
export type SubVerticalErrors = string[] | Record<string, Record<string, string[]>>

const BASE = '/catalogs/verticals/'

export function listVerticals(params: ListParams) {
  return api<Paginated<Vertical>>(BASE + listQuery(params))
}

export function getVerticalDefaults() {
  return api<SubVerticalDefaults>(`${BASE}defaults/`)
}

export function createVertical(data: VerticalInput) {
  return api<Vertical>(BASE, { method: 'POST', body: JSON.stringify(data) })
}

export function updateVertical(id: number, data: VerticalInput) {
  return api<Vertical>(`${BASE}${id}/`, { method: 'PATCH', body: JSON.stringify(data) })
}

export function deleteVertical(id: number) {
  return api<void>(`${BASE}${id}/`, { method: 'DELETE' })
}
