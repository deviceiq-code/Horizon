import { api, listQuery, type ListParams, type Paginated } from '@/api'
import type { AccountManagerRef } from '@/modules/account-managers/api'

export interface Customer {
  id: number
  name: string
  trade_name: string
  /** Uppercase, without punctuation (CNPJ/CPF in Brazil) */
  tax_id: string
  /** ISO 3166-1 alpha-2 */
  country: string
  email: string
  phone: string
  postal_code: string
  street: string
  number: string
  complement: string
  district: string
  city: string
  state: string
  /** Exactly one, required (null only while editing a new customer) */
  primary_account_manager: number | null
  primary_account_manager_name: string
  /** Any number; never includes the primary one */
  secondary_account_managers: number[]
  /** Same secondary managers with names, sorted by name (read-only) */
  secondary_account_managers_detail: AccountManagerRef[]
  is_active: boolean
  notes: string
  keywords: string[]
  created_at: string
  updated_at: string
}

export type CustomerInput = Omit<
  Customer,
  | 'id'
  | 'primary_account_manager_name'
  | 'secondary_account_managers_detail'
  | 'created_at'
  | 'updated_at'
>

const BASE = '/customers/'

export function listCustomers(params: ListParams) {
  return api<Paginated<Customer>>(BASE + listQuery(params))
}

export function createCustomer(data: CustomerInput) {
  return api<Customer>(BASE, { method: 'POST', body: JSON.stringify(data) })
}

export function updateCustomer(id: number, data: CustomerInput) {
  return api<Customer>(`${BASE}${id}/`, { method: 'PATCH', body: JSON.stringify(data) })
}

export function deleteCustomer(id: number) {
  return api<void>(`${BASE}${id}/`, { method: 'DELETE' })
}
