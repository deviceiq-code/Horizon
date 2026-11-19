import { api, listQuery, type ListParams, type Paginated } from '@/api'

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
  account_manager: number | null
  account_manager_name: string | null
  is_active: boolean
  notes: string
  created_at: string
  updated_at: string
}

export type CustomerInput = Omit<
  Customer,
  'id' | 'account_manager_name' | 'created_at' | 'updated_at'
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
