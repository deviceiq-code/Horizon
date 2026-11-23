import { api, listQuery, type ListParams, type Paginated } from '@/api'
import type { VerticalRef } from '@/modules/catalogs/verticals/api'

/** Own: run by Horizon; outsourced: by a service provider of warehousing. */
export type Ownership = 'own' | 'outsourced'

export interface Warehouse {
  id: number
  name: string
  ownership: Ownership
  /** Outsourced only (required then); null when own */
  service_provider: number | null
  /** Read-only: who runs it (trade name when it has one) */
  service_provider_detail: { id: number; name: string } | null
  /** Business verticals it serves (ids; at least one; only enabled ones can be added) */
  verticals: number[]
  /** The same verticals with names, sorted by name (read-only) */
  verticals_detail: VerticalRef[]
  contact_name: string
  email: string
  phone: string
  /** ISO 3166-1 alpha-2 */
  country: string
  postal_code: string
  street: string
  number: string
  complement: string
  district: string
  city: string
  state: string
  is_active: boolean
  notes: string
  keywords: string[]
  created_at: string
  updated_at: string
}

export type WarehouseInput = Omit<
  Warehouse,
  'id' | 'service_provider_detail' | 'verticals_detail' | 'created_at' | 'updated_at'
>

const BASE = '/inventory/warehouses/'

/** Filters: `ownership`, `vertical`, `service_provider`, `name`, `location`, `is_active`. */
export function listWarehouses(params: ListParams) {
  return api<Paginated<Warehouse>>(BASE + listQuery(params))
}

export function createWarehouse(data: WarehouseInput) {
  return api<Warehouse>(BASE, { method: 'POST', body: JSON.stringify(data) })
}

export function updateWarehouse(id: number, data: WarehouseInput) {
  return api<Warehouse>(`${BASE}${id}/`, { method: 'PATCH', body: JSON.stringify(data) })
}

export function deleteWarehouse(id: number) {
  return api<void>(`${BASE}${id}/`, { method: 'DELETE' })
}
