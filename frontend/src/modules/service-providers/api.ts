import { api, listQuery, type ListParams, type Paginated } from '@/api'

/** What a provider can do (backend `service_providers.models.ServiceKind`), in display order. */
export const SERVICE_KINDS = [
  'warehousing',
  'transport',
  'inspection',
  'refurbishment',
  'repair',
  'data_erasure',
  'packaging',
  'sales',
  'disposal',
] as const

export type ServiceKind = (typeof SERVICE_KINDS)[number]

export const SERVICE_ICONS: Record<ServiceKind, string> = {
  warehousing: 'mdi-warehouse',
  transport: 'mdi-truck-outline',
  inspection: 'mdi-clipboard-check-outline',
  refurbishment: 'mdi-autorenew',
  repair: 'mdi-wrench-outline',
  data_erasure: 'mdi-harddisk-remove',
  packaging: 'mdi-package-variant-closed',
  sales: 'mdi-gavel',
  disposal: 'mdi-recycle',
}

export interface ServiceProvider {
  id: number
  name: string
  trade_name: string
  /** Uppercase, without punctuation (CNPJ/CPF in Brazil) */
  tax_id: string
  /** ISO 3166-1 alpha-2 */
  country: string
  /** At least one, in SERVICE_KINDS order */
  services: ServiceKind[]
  contact_name: string
  email: string
  phone: string
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
  /** Warehouses it runs (read-only) */
  warehouses_count: number
  created_at: string
  updated_at: string
}

export type ServiceProviderInput = Omit<
  ServiceProvider,
  'id' | 'warehouses_count' | 'created_at' | 'updated_at'
>

const BASE = '/service-providers/'

/** Filters: `service` (a ServiceKind), `is_active`. */
export function listServiceProviders(params: ListParams) {
  return api<Paginated<ServiceProvider>>(BASE + listQuery(params))
}

export function createServiceProvider(data: ServiceProviderInput) {
  return api<ServiceProvider>(BASE, { method: 'POST', body: JSON.stringify(data) })
}

export function updateServiceProvider(id: number, data: ServiceProviderInput) {
  return api<ServiceProvider>(`${BASE}${id}/`, { method: 'PATCH', body: JSON.stringify(data) })
}

export function deleteServiceProvider(id: number) {
  return api<void>(`${BASE}${id}/`, { method: 'DELETE' })
}
