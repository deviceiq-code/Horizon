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
  /** Accessories tracked by quantity */
  accessory_model: number | null
  accessory_model_label: string | null
  quantity: number | null
  accessory_condition: '' | 'good' | 'scrap'
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

// --- Phase 2: appointments, receiving lots, occurrences, accessory balances --------------------

export type AppointmentKind = 'receiving' | 'shipping'
export const APPOINTMENT_STATUSES = [
  'scheduled',
  'confirmed',
  'in_progress',
  'done',
  'cancelled',
  'no_show',
] as const
export type AppointmentStatus = (typeof APPOINTMENT_STATUSES)[number]

export interface ExpectedItem {
  id?: number
  asset_model: number | null
  asset_model_label: string
  tracking: 'unit' | 'quantity' | null
  serial: string
  quantity: number | null
}

export interface Appointment {
  id: number
  code: string
  kind: AppointmentKind
  warehouse: number
  warehouse_detail: { id: number; code: string; name: string }
  customer: number | null
  customer_name: string | null
  starts_at: string
  ends_at: string
  status: AppointmentStatus
  carrier: number | null
  carrier_detail: { id: number; name: string } | null
  carrier_name: string
  vehicle_plate: string
  driver_name: string
  expected_volumes: number | null
  notes: string
  /** Codes of other appointments of the warehouse at the same time (only a warning) */
  conflicts: string[]
  lot: { id: number; code: string; status: LotStatus } | null
  /** Absent for users who may not see it (blind count, RN-17) */
  expected_items?: ExpectedItem[]
  created_by_name: string
  created_at: string
  updated_at: string
}

export interface AppointmentInput {
  kind: AppointmentKind
  warehouse: number | null
  customer: number | null
  starts_at: string
  ends_at: string
  carrier: number | null
  carrier_name: string
  vehicle_plate: string
  driver_name: string
  expected_volumes: number | null
  notes: string
  expected_items?: { asset_model: number; serial: string; quantity: number }[]
}

export interface ParsedRow extends ExpectedItem {
  line: number
  errors: string[]
}

/** Filters: `kind`, `warehouse`, `status`, `customer`, `from`, `to` (YYYY-MM-DD). */
export function listAppointments(params: ListParams) {
  return api<Paginated<Appointment>>(`${BASE}/appointments/` + listQuery(params))
}

export function getAppointment(id: number) {
  return api<Appointment>(`${BASE}/appointments/${id}/`)
}

export function createAppointment(data: AppointmentInput) {
  return api<Appointment>(`${BASE}/appointments/`, { method: 'POST', body: JSON.stringify(data) })
}

export function updateAppointment(id: number, data: Partial<AppointmentInput>) {
  return api<Appointment>(`${BASE}/appointments/${id}/`, {
    method: 'PATCH',
    body: JSON.stringify(data),
  })
}

export function deleteAppointment(id: number) {
  return api<void>(`${BASE}/appointments/${id}/`, { method: 'DELETE' })
}

export function setAppointmentStatus(id: number, status: AppointmentStatus) {
  return api<Appointment>(`${BASE}/appointments/${id}/status/`, {
    method: 'POST',
    body: JSON.stringify({ status }),
  })
}

export function parseExpected(text: string) {
  return api<{ rows: ParsedRow[] }>(`${BASE}/appointments/parse-expected/`, {
    method: 'POST',
    body: JSON.stringify({ text }),
  })
}

export type LotStatus = 'open' | 'reconciling' | 'closed'

export interface Lot {
  id: number
  code: string
  warehouse: number
  warehouse_detail: { id: number; code: string; name: string }
  customer: number
  customer_name: string
  appointment: number | null
  appointment_detail: { id: number; code: string } | null
  dock: number
  dock_detail: LocationRef
  fiscal_document_number: string
  status: LotStatus
  notes: string
  is_scheduled: boolean
  units_count: number
  open_occurrences: number
  opened_by_name: string
  opened_at: string
  closed_by_name: string | null
  closed_at: string | null
}

export interface LotReceived {
  units: Asset[]
  accessories: MovementEvent[]
}

export const OCCURRENCE_KINDS = [
  'shortage',
  'surplus',
  'serial_mismatch',
  'model_mismatch',
  'transport_damage',
  'location_mismatch',
  'lost',
] as const
export type OccurrenceKind = (typeof OCCURRENCE_KINDS)[number]
export type OccurrenceStatus = 'open' | 'resolved' | 'accepted'

export interface Occurrence {
  id: number
  kind: OccurrenceKind
  lot: number
  lot_code: string
  asset: number | null
  asset_code: string | null
  asset_model: number | null
  asset_model_label: string | null
  quantity: number
  expected_serial: string
  received_serial: string
  description: string
  responsible: number | null
  responsible_name: string | null
  due_date: string | null
  status: OccurrenceStatus
  resolution: string
  resolved_by_name: string | null
  resolved_at: string | null
  automatic: boolean
  attachments_count: number
  created_at: string
}

export const ATTACHMENT_KINDS = [
  'fiscal_document',
  'package_photo',
  'damage_photo',
  'no_serial_photo',
  'occurrence',
  'other',
] as const
export type AttachmentKind = (typeof ATTACHMENT_KINDS)[number]

export interface LotAttachment {
  id: number
  kind: AttachmentKind
  name: string
  size: number
  content_type: string
  asset: number | null
  asset_code: string | null
  occurrence: number | null
  uploaded_by_name: string
  uploaded_at: string
}

export interface AccessoryBalance {
  id: number
  asset_model: number
  asset_model_label: string
  asset_class_name: string
  container: number | null
  container_code: string | null
  location_detail: LocationRef
  warehouse: { id: number; code: string; name: string } | null
  condition: 'good' | 'scrap'
  quantity: number
  updated_at: string
}

/** Filters: `status`, `warehouse`, `customer`. */
export function listLots(params: ListParams) {
  return api<Paginated<Lot>>(`${BASE}/lots/` + listQuery(params))
}

export function getLot(id: number) {
  return api<Lot>(`${BASE}/lots/${id}/`)
}

export function openLot(data: {
  appointment?: number | null
  warehouse?: number | null
  customer?: number | null
  dock_code: string
  fiscal_document_number: string
  notes: string
}) {
  return api<Lot>(`${BASE}/lots/`, { method: 'POST', body: JSON.stringify(data) })
}

export function updateLot(id: number, data: { fiscal_document_number?: string; notes?: string }) {
  return api<Lot>(`${BASE}/lots/${id}/`, { method: 'PATCH', body: JSON.stringify(data) })
}

/** One unit read at triage; `photo` required without a serial number. */
export function triageUnit(
  lotId: number,
  data: {
    asset_model: number
    horizon_id: string
    serial: string
    no_serial_reason: string
    container_code: string
    photo?: File | null
  },
) {
  const body = new FormData()
  for (const [key, value] of Object.entries(data)) {
    if (value instanceof File) body.append(key, value)
    else if (value !== null && value !== undefined) body.append(key, String(value))
  }
  return api<Asset>(`${BASE}/lots/${lotId}/units/`, { method: 'POST', body })
}

export function triageAccessories(
  lotId: number,
  data: {
    asset_model: number
    quantity: number
    container_code: string
    damaged_quantity: number
    scrap_code: string
  },
) {
  return api<LotReceived>(`${BASE}/lots/${lotId}/accessories/`, {
    method: 'POST',
    body: JSON.stringify(data),
  })
}

export function lotReceived(lotId: number) {
  return api<LotReceived>(`${BASE}/lots/${lotId}/received/`)
}

/** Not for receivers (blind count): 403. */
export function lotExpected(lotId: number) {
  return api<ExpectedItem[]>(`${BASE}/lots/${lotId}/expected/`)
}

export function reconcileLot(lotId: number) {
  return api<Lot>(`${BASE}/lots/${lotId}/reconcile/`, { method: 'POST', body: '{}' })
}

export function closeLot(lotId: number) {
  return api<Lot>(`${BASE}/lots/${lotId}/close/`, { method: 'POST', body: '{}' })
}

export function listLotAttachments(lotId: number) {
  return api<LotAttachment[]>(`${BASE}/lots/${lotId}/attachments/`)
}

export function uploadLotAttachment(
  lotId: number,
  file: File,
  kind: AttachmentKind,
  occurrence?: number,
) {
  const body = new FormData()
  body.append('file', file)
  body.append('kind', kind)
  if (occurrence) body.append('occurrence', String(occurrence))
  return api<LotAttachment[]>(`${BASE}/lots/${lotId}/attachments/`, { method: 'POST', body })
}

export function deleteLotAttachment(lotId: number, attachmentId: number) {
  return api<void>(`${BASE}/lots/${lotId}/attachments/${attachmentId}/`, { method: 'DELETE' })
}

export function lotAttachmentUrl(lotId: number, attachmentId: number, inline = false) {
  return `/api${BASE}/lots/${lotId}/attachments/${attachmentId}/download/${inline ? '?inline=1' : ''}`
}

/** Filters: `lot`, `status`, `kind`. */
export function listOccurrences(params: ListParams) {
  return api<Paginated<Occurrence>>(`${BASE}/occurrences/` + listQuery(params))
}

export function createOccurrence(data: {
  lot: number
  kind: OccurrenceKind
  quantity: number
  description: string
  due_date: string | null
}) {
  return api<Occurrence>(`${BASE}/occurrences/`, { method: 'POST', body: JSON.stringify(data) })
}

export function resolveOccurrence(id: number, resolution: string) {
  return api<Occurrence>(`${BASE}/occurrences/${id}/resolve/`, {
    method: 'POST',
    body: JSON.stringify({ resolution }),
  })
}

export function acceptOccurrence(id: number, resolution: string) {
  return api<Occurrence>(`${BASE}/occurrences/${id}/accept/`, {
    method: 'POST',
    body: JSON.stringify({ resolution }),
  })
}

/** Filters: `asset_model`, `warehouse`, `condition`. */
export function listAccessoryBalances(params: ListParams) {
  return api<Paginated<AccessoryBalance>>(`${BASE}/accessory-balances/` + listQuery(params))
}
