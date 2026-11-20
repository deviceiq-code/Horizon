/**
 * Account managers: active users with the "Account Manager" role (managed in Administration →
 * Users). This read-only list feeds the pickers of other modules (customers…).
 */
import { api, listQuery, type ListParams, type Paginated } from '@/api'
import type { VerticalRef } from '@/modules/catalogs/verticals/api'

export interface AccountManager {
  /** The user's id */
  id: number
  /** "First Last" (or "Last, First", as set in the system settings) */
  full_name: string
  first_name: string
  last_name: string
  email: string
  photo_version: string | null
  /** Business verticals they work in (set by administrators on the user) */
  verticals_detail: VerticalRef[]
}

/** Minimal reference to an account manager, as other modules display it. */
export type AccountManagerRef = Pick<AccountManager, 'id' | 'full_name'>

/** ?search= (name, email, vertical), ?vertical=<id> (in filters), ordering by name. */
export function listAccountManagers(params: ListParams) {
  return api<Paginated<AccountManager>>('/account-managers/' + listQuery(params))
}
