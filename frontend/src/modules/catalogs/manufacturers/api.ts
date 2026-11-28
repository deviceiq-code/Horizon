import { api, listQuery, type ListParams, type Paginated } from '@/api'
import type { EntityRef } from '@/modules/business-entities/api'

/** The three ratings that make up a manufacturer's remarketing rating (0–5 stars, half steps). */
export const MANUFACTURER_RATINGS = ['reputation', 'product_quality', 'after_sales'] as const

export type ManufacturerRating = (typeof MANUFACTURER_RATINGS)[number]

export interface Manufacturer {
  id: number
  name: string
  /** The business entity behind the brand (optional) */
  business_entity: number | null
  business_entity_detail: EntityRef | null
  /** 0–5 stars as decimal strings ("3.5"); not filled in = "0.0" */
  reputation: string
  product_quality: string
  after_sales: string
  /** Average of the three ratings, computed by the API ("3.83"); read-only */
  remarketing_average: string
  is_enabled: boolean
  keywords: string[]
  created_at: string
  updated_at: string
}

export type ManufacturerInput = Pick<
  Manufacturer,
  'name' | 'business_entity' | ManufacturerRating | 'is_enabled' | 'keywords'
>

const BASE = '/catalogs/manufacturers/'

export function listManufacturers(params: ListParams) {
  return api<Paginated<Manufacturer>>(BASE + listQuery(params))
}

export function createManufacturer(data: ManufacturerInput) {
  return api<Manufacturer>(BASE, { method: 'POST', body: JSON.stringify(data) })
}

export function updateManufacturer(id: number, data: ManufacturerInput) {
  return api<Manufacturer>(`${BASE}${id}/`, { method: 'PATCH', body: JSON.stringify(data) })
}

export function deleteManufacturer(id: number) {
  return api<void>(`${BASE}${id}/`, { method: 'DELETE' })
}
