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
  /** IDs of the account managers who may work in this vertical (all sub-verticals) */
  account_managers: number[]
  /** Same managers with names, sorted by name (read-only) */
  account_managers_detail: AccountManagerRef[]
  is_enabled: boolean
  notes: string
  /** General first, then by name */
  sub_verticals: SubVertical[]
  created_at: string
  updated_at: string
}

/** Sending sub_verticals replaces the whole list (it must include the general one). */
export type VerticalInput = Pick<
  Vertical,
  'name' | 'account_managers' | 'is_enabled' | 'notes' | 'sub_verticals'
>

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
