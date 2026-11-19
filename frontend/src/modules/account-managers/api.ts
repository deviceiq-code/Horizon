import { api, listQuery, type ListParams, type Paginated } from '@/api'

export interface AccountManager {
  id: number
  full_name: string
  email: string
  created_at: string
  updated_at: string
}

export type AccountManagerInput = Pick<AccountManager, 'full_name' | 'email'>

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
