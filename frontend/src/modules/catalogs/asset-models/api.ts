import { api, listQuery, type ListParams, type Paginated } from '@/api'
import type { SpecField } from '@/modules/catalogs/asset-classes/api'

/** How the inventory controls a model: each unit with its Horizon ID, or a balance. */
export type Tracking = 'unit' | 'quantity'

/** A stored specification value (the asset class's field + its value as text). */
export type SpecValue = SpecField & { value: string }

/** An item expected with each unit; a missing essential one makes it incomplete ("I"). */
export interface KitItem {
  item: string
  essential: boolean
}

export interface AssetModel {
  id: number
  manufacturer: number
  manufacturer_name: string
  name: string
  asset_class: number
  asset_class_detail: { id: number; name: string; icon: string; has_template: boolean }
  /** Values of the asset class's template (defaults for the model's units) */
  spec_values: SpecValue[]
  tracking: Tracking
  /** Regular expression the serial numbers read at triage must match (empty: any) */
  serial_regex: string
  /** Items expected with each unit (checked at inspection) */
  kit_checklist: KitItem[]
  /** Checks run at inspection */
  test_script: string[]
  has_storage: boolean
  keywords: string[]
  notes: string
  is_enabled: boolean
  /** Units in stock (read-only) */
  assets_count: number
  created_at: string
  updated_at: string
}

export interface AssetModelInput {
  manufacturer: number | null
  name: string
  asset_class: number | null
  /** {field key: value as text} */
  specs: Record<string, string>
  tracking: Tracking
  serial_regex: string
  kit_checklist: KitItem[]
  test_script: string[]
  has_storage: boolean
  keywords: string[]
  notes: string
  is_enabled: boolean
}

const BASE = '/catalogs/asset-models/'

/** Filters: `manufacturer`, `asset_class`, `tracking`, `name`, `is_enabled`. */
export function listAssetModels(params: ListParams) {
  return api<Paginated<AssetModel>>(BASE + listQuery(params))
}

export function createAssetModel(data: AssetModelInput) {
  return api<AssetModel>(BASE, { method: 'POST', body: JSON.stringify(data) })
}

export function updateAssetModel(id: number, data: AssetModelInput) {
  return api<AssetModel>(`${BASE}${id}/`, { method: 'PATCH', body: JSON.stringify(data) })
}

export function deleteAssetModel(id: number) {
  return api<void>(`${BASE}${id}/`, { method: 'DELETE' })
}
