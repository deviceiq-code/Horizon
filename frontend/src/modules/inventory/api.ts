import { api, listQuery, type ListParams, type Paginated } from '@/api'
import type { SpecValue } from '@/modules/catalogs/asset-models/api'

/** The asset's life in the warehouse (backend inventory/states.py). */
export const ASSET_STATUSES = [
  'in_triage',
  'awaiting_inspection',
  'in_inspection',
  'blocked',
  'available',
  'reserved',
  'scrap',
  'in_transit',
  'written_off',
] as const
export type AssetStatus = (typeof ASSET_STATUSES)[number]

/** Kinds of area of a location; each takes some statuses (`accepted_statuses`). */
export const AREA_TYPES = [
  'dock',
  'inspection_queue',
  'bench',
  'quarantine',
  'stock',
  'scrap',
  'shipping',
] as const
export type AreaType = (typeof AREA_TYPES)[number] | 'virtual_transit'

export const CONTAINER_KINDS = ['box', 'cage', 'pallet'] as const
export type ContainerKind = (typeof CONTAINER_KINDS)[number]

export const NO_SERIAL_REASONS = ['unreadable', 'needs_power_on', 'item_has_none'] as const
export type NoSerialReason = (typeof NO_SERIAL_REASONS)[number]

export interface LocationRef {
  id: number
  code: string
  area_type: AreaType
}

export interface Location {
  id: number
  warehouse: number | null
  parent: number | null
  /** Typed by the user; the code is the parent's (or warehouse's) code + "-" + segment */
  segment: string
  code: string
  area_type: AreaType
  accepted_statuses: AssetStatus[]
  description: string
  is_active: boolean
  children_count: number
  assets_count: number
  containers_count: number
  created_at: string
  updated_at: string
}

export interface LocationNode extends Location {
  children: LocationNode[]
}

export interface LocationInput {
  warehouse?: number | null
  parent?: number | null
  segment?: string
  area_type?: AreaType
  description?: string
  is_active?: boolean
}

export interface Container {
  id: number
  code: string
  kind: ContainerKind
  current_location: number
  current_location_detail: LocationRef
  description: string
  is_active: boolean
  assets_count: number
  created_at: string
  updated_at: string
}

export interface Asset {
  id: number
  horizon_id: string
  asset_model: number
  asset_model_detail: {
    id: number
    name: string
    manufacturer_name: string
    asset_class: number
    asset_class_name: string
    asset_class_icon: string
    tracking: 'unit' | 'quantity'
    has_storage: boolean
  }
  specs: SpecValue[]
  serial: string
  serial_status: 'captured' | 'pending' | 'none'
  no_serial_reason: NoSerialReason | ''
  other_ids: Record<string, string>
  status: AssetStatus
  warehouse: { id: number; code: string; name: string } | null
  current_location: number
  current_location_detail: LocationRef
  current_container: number | null
  current_container_detail: { id: number; code: string } | null
  held_for_dispute: boolean
  parent_asset: number | null
  notes: string
  created_at: string
  updated_at: string
}

export interface MovementEvent {
  id: number
  kind: string
  asset: number | null
  asset_code: string | null
  container: number | null
  container_code: string | null
  from_location_code: string | null
  to_location_code: string | null
  from_container_code: string | null
  to_container_code: string | null
  status_before: AssetStatus | ''
  status_after: AssetStatus | ''
  user: number
  user_name: string
  at: string
  reason: string
  document_ref: string
  parent_event: number | null
  reverses: number | null
}

export type AssetDetail = Asset & { events: MovementEvent[] }

export interface LabelRange {
  id: number
  first_number: number
  last_number: number
  first_code: string
  last_code: string
  size: number
  reserved_by: number
  reserved_by_name: string
  reserved_at: string
}

export type LookupResult =
  | { kind: 'asset'; item: Asset }
  | { kind: 'container'; item: Container }
  | { kind: 'location'; item: Location }

const BASE = '/inventory'

// --- Locations ---------------------------------------------------------------------------------

export function listLocations(params: ListParams) {
  return api<Paginated<Location>>(`${BASE}/locations/` + listQuery(params))
}

export function locationTree(warehouse: number) {
  return api<LocationNode[]>(`${BASE}/locations/tree/?warehouse=${warehouse}`)
}

export function createLocation(data: LocationInput) {
  return api<Location>(`${BASE}/locations/`, { method: 'POST', body: JSON.stringify(data) })
}

export function updateLocation(id: number, data: LocationInput) {
  return api<Location>(`${BASE}/locations/${id}/`, {
    method: 'PATCH',
    body: JSON.stringify(data),
  })
}

export function deleteLocation(id: number) {
  return api<void>(`${BASE}/locations/${id}/`, { method: 'DELETE' })
}

// --- Containers --------------------------------------------------------------------------------

/** Filters: `kind`, `location`, `warehouse`, `is_active`. */
export function listContainers(params: ListParams) {
  return api<Paginated<Container>>(`${BASE}/containers/` + listQuery(params))
}

export function createContainer(data: {
  kind: ContainerKind
  current_location: number
  description: string
}) {
  return api<Container>(`${BASE}/containers/`, { method: 'POST', body: JSON.stringify(data) })
}

export function updateContainer(
  id: number,
  data: { kind?: ContainerKind; description?: string; is_active?: boolean },
) {
  return api<Container>(`${BASE}/containers/${id}/`, {
    method: 'PATCH',
    body: JSON.stringify(data),
  })
}

export function deleteContainer(id: number) {
  return api<void>(`${BASE}/containers/${id}/`, { method: 'DELETE' })
}

export function reprintContainer(id: number) {
  return api<Container>(`${BASE}/containers/${id}/reprint/`, { method: 'POST', body: '{}' })
}

// --- Assets ----------------------------------------------------------------------------------

/** Filters: `status`, `warehouse`, `location`, `container`, `asset_model`, `asset_class`, `name`. */
export function listAssets(params: ListParams) {
  return api<Paginated<Asset>>(`${BASE}/assets/` + listQuery(params))
}

export function getAsset(id: number) {
  return api<AssetDetail>(`${BASE}/assets/${id}/`)
}

export function updateAsset(
  id: number,
  data: { notes?: string; other_ids?: Record<string, string> },
) {
  return api<Asset>(`${BASE}/assets/${id}/`, { method: 'PATCH', body: JSON.stringify(data) })
}

/** Manual entry at a dock (administrators, until triage). `location`: code read. */
export function registerEntry(data: {
  asset_model: number
  location: string
  horizon_id: string
  serial: string
  no_serial_reason: string
  reason: string
}) {
  return api<Asset>(`${BASE}/assets/`, { method: 'POST', body: JSON.stringify(data) })
}

export function reprintAsset(id: number) {
  return api<Asset>(`${BASE}/assets/${id}/reprint/`, { method: 'POST', body: '{}' })
}

// --- Movements and lookup ----------------------------------------------------------------------

export function lookupCode(code: string) {
  return api<LookupResult>(`${BASE}/lookup/?code=${encodeURIComponent(code)}`)
}

export function moveByCodes(objectCode: string, destinationCode: string, reason = '') {
  return api<MovementEvent>(`${BASE}/movements/`, {
    method: 'POST',
    body: JSON.stringify({
      object_code: objectCode,
      destination_code: destinationCode,
      reason,
    }),
  })
}

export function myLatestMovements() {
  return api<Paginated<MovementEvent>>(`${BASE}/movements/?mine=true&page_size=10`)
}

export function reverseMovement(id: number, reason: string) {
  return api<MovementEvent>(`${BASE}/movements/${id}/reverse/`, {
    method: 'POST',
    body: JSON.stringify({ reason }),
  })
}

// --- Labels ----------------------------------------------------------------------------------

export function listLabelRanges(params: ListParams) {
  return api<Paginated<LabelRange>>(`${BASE}/label-ranges/` + listQuery(params))
}

export function reserveLabelRange(count: number) {
  return api<LabelRange>(`${BASE}/label-ranges/`, {
    method: 'POST',
    body: JSON.stringify({ count }),
  })
}
