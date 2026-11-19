import { api, listQuery, type ListParams, type Paginated } from '@/api'
import type { VerticalRef } from '@/modules/catalogs/verticals/api'

export interface AccountManager {
  id: number
  first_name: string
  /** Optional */
  last_name: string
  /** "First Last", composed by the API (read-only) */
  full_name: string
  email: string
  /** IDs of the business verticals this account manager works in */
  verticals: number[]
  /** Same verticals with name and enabled flag, sorted by name (read-only) */
  verticals_detail: VerticalRef[]
  /** Changes with every new photo; null without one (see accountManagerPhotoUrl) */
  photo_version: string | null
  created_at: string
  updated_at: string
}

export type AccountManagerInput = Pick<
  AccountManager,
  'first_name' | 'last_name' | 'email' | 'verticals'
>

/** Minimal reference to an account manager, as other modules display it. */
export type AccountManagerRef = Pick<AccountManager, 'id' | 'full_name'>

const BASE = '/account-managers/'

export function listAccountManagers(params: ListParams) {
  return api<Paginated<AccountManager>>(BASE + listQuery(params))
}

export function createAccountManager(data: AccountManagerInput) {
  return api<AccountManager>(BASE, { method: 'POST', body: JSON.stringify(data) })
}

export function updateAccountManager(id: number, data: AccountManagerInput) {
  return api<AccountManager>(`${BASE}${id}/`, { method: 'PATCH', body: JSON.stringify(data) })
}

export function deleteAccountManager(id: number) {
  return api<void>(`${BASE}${id}/`, { method: 'DELETE' })
}

/** The photo's address; the version makes the browser fetch a new photo. */
export function accountManagerPhotoUrl(id: number, version: string) {
  return `/api${BASE}${id}/photo/?v=${version}`
}

/** Sets or replaces the photo (send a square picture: utils/image.squareImage). */
export function uploadAccountManagerPhoto(id: number, file: File) {
  const body = new FormData()
  body.append('file', file)
  return api<AccountManager>(`${BASE}${id}/photo/`, { method: 'POST', body })
}

export function deleteAccountManagerPhoto(id: number) {
  return api<void>(`${BASE}${id}/photo/`, { method: 'DELETE' })
}
