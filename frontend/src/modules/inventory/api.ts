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
  /** Grade of its current inspection report ("B1C"; empty before) */
  condition_grade: string
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

// --- Phase 3: grades, penalty table, erasure tools, inspection reports -------------------------

export type GradeDomain = 'conservation' | 'functioning' | 'completeness'
/** The fixed codes of each grade domain, in order ("B1C") */
export const GRADE_CODES: Record<GradeDomain, string[]> = {
  conservation: ['A', 'B', 'C', 'D'],
  functioning: ['1', '2', '3', '0'],
  completeness: ['C', 'P', 'I'],
}

export interface GradeLevel {
  id: number
  domain: GradeDomain
  code: string
  name: string
  description: string
  order: number
}

export const FINDING_KINDS = [
  'access_block',
  'customization',
  'heavy_cleaning',
  'missing_item',
  'damage',
] as const
export type FindingKind = (typeof FINDING_KINDS)[number]
export const BLOCK_TYPES = [
  'cloud_account',
  'mdm',
  'bios_password',
  'factory_reset',
  'other',
] as const
export type BlockType = (typeof BLOCK_TYPES)[number]
export const ERASURE_METHODS = ['clear', 'purge', 'destroy', 'crypto_erase'] as const
export type ErasureMethod = (typeof ERASURE_METHODS)[number]
export const PHOTO_KINDS = ['front', 'back', 'side', 'screen', 'damage', 'serial', 'other'] as const
export type PhotoKind = (typeof PHOTO_KINDS)[number]
export type ReportStatus = 'draft' | 'awaiting_approval' | 'approved' | 'superseded'
export type Destination = 'available' | 'blocked' | 'scrap'

export interface PenaltyRate {
  id: number
  asset_class: number
  asset_class_name: string
  finding_kind: FindingKind
  /** Decimal as text ("150.00") */
  value: string
  valid_from: string
  valid_to: string | null
  created_at: string
  updated_at: string
}

export interface ErasureTool {
  id: number
  name: string
  version: string
  methods: ErasureMethod[]
  asset_classes: number[]
  asset_classes_detail: { id: number; name: string }[]
  notes: string
  is_active: boolean
  created_at: string
  updated_at: string
}

export interface LotErasureToolRow {
  asset_class: number
  asset_class_name: string
  definition: {
    asset_class: number
    tool: number
    tool_label: string
    method: ErasureMethod
    defined_by_name: string
    defined_at: string
  } | null
  tools: { id: number; label: string; methods: ErasureMethod[] }[]
}

export interface ReportPhoto {
  id: number
  kind: PhotoKind
  name: string
  size: number
  description: string
  uploaded_at: string
}

export interface Finding {
  id: number
  kind: FindingKind
  block_type: BlockType | ''
  item: string
  description: string
  value: string | null
  value_overridden: boolean
  value_justification: string
  status: string
  automatic: boolean
}

export interface ErasureCertificate {
  id: number
  disk_serial: string
  tool_label: string
  tool_version: string
  method: ErasureMethod
  result: 'success' | 'failure'
  removed_disk: number | null
  removed_disk_code: string | null
  operator_name: string
  at: string
  name: string
}

export interface ReportSummary {
  id: number
  asset: number
  asset_code: string
  asset_model_label: string
  asset_class_icon: string
  serial: string
  customer_name: string | null
  lot_code: string | null
  version: number
  is_current: boolean
  status: ReportStatus
  technician: number
  technician_name: string
  started_at: string
  finished_at: string | null
  grade: string
  recommended_destination: Destination | ''
  approved_at: string | null
  sent_to_customer_at: string | null
}

export interface InspectionReport extends ReportSummary {
  asset_detail: Asset
  conservation: string
  functioning: string
  completeness: string
  failed_components: string
  irreparable: boolean
  missing_items: string[]
  checklist_done: boolean
  test_results: Record<string, 'pass' | 'fail' | 'na'>
  cleaning: 'standard' | 'heavy'
  notes: string
  review_notes: string
  approved_by_name: string | null
  new_version_reason: string
  kit_checklist: { item: string; essential: boolean }[]
  test_script: string[]
  has_storage: boolean
  required_photo_kinds: PhotoKind[]
  photos: ReportPhoto[]
  findings: Finding[]
  erasures: ErasureCertificate[]
  lot_tool: LotErasureToolRow['definition']
  suggestions: { functioning: string; completeness: string; destination: Destination }
  /** What still prevents submitting (draft only) */
  problems: string[]
}

export type ReportDraft = Partial<
  Pick<
    InspectionReport,
    | 'conservation'
    | 'functioning'
    | 'completeness'
    | 'failed_components'
    | 'irreparable'
    | 'missing_items'
    | 'checklist_done'
    | 'test_results'
    | 'cleaning'
    | 'notes'
  >
>

export function listGradeLevels() {
  return api<GradeLevel[]>(`${BASE}/grade-levels/`)
}

export function updateGradeLevel(id: number, data: { name?: string; description?: string }) {
  return api<GradeLevel>(`${BASE}/grade-levels/${id}/`, {
    method: 'PATCH',
    body: JSON.stringify(data),
  })
}

/** Filters: `asset_class`, `finding_kind`, `current`. */
export function listPenaltyRates(params: ListParams) {
  return api<Paginated<PenaltyRate>>(`${BASE}/penalty-rates/` + listQuery(params))
}

export type PenaltyRateInput = Pick<
  PenaltyRate,
  'finding_kind' | 'value' | 'valid_from' | 'valid_to'
> & { asset_class: number | null }

export function createPenaltyRate(data: PenaltyRateInput) {
  return api<PenaltyRate>(`${BASE}/penalty-rates/`, { method: 'POST', body: JSON.stringify(data) })
}

export function updatePenaltyRate(id: number, data: PenaltyRateInput) {
  return api<PenaltyRate>(`${BASE}/penalty-rates/${id}/`, {
    method: 'PATCH',
    body: JSON.stringify(data),
  })
}

export function deletePenaltyRate(id: number) {
  return api<void>(`${BASE}/penalty-rates/${id}/`, { method: 'DELETE' })
}

/** Filters: `asset_class`, `is_active`. */
export function listErasureTools(params: ListParams) {
  return api<Paginated<ErasureTool>>(`${BASE}/erasure-tools/` + listQuery(params))
}

export type ErasureToolInput = Pick<
  ErasureTool,
  'name' | 'version' | 'methods' | 'asset_classes' | 'notes' | 'is_active'
>

export function createErasureTool(data: ErasureToolInput) {
  return api<ErasureTool>(`${BASE}/erasure-tools/`, { method: 'POST', body: JSON.stringify(data) })
}

export function updateErasureTool(id: number, data: ErasureToolInput) {
  return api<ErasureTool>(`${BASE}/erasure-tools/${id}/`, {
    method: 'PATCH',
    body: JSON.stringify(data),
  })
}

export function deleteErasureTool(id: number) {
  return api<void>(`${BASE}/erasure-tools/${id}/`, { method: 'DELETE' })
}

export function lotErasureTools(lotId: number) {
  return api<LotErasureToolRow[]>(`${BASE}/lots/${lotId}/erasure-tools/`)
}

export function setLotErasureTools(
  lotId: number,
  definitions: { asset_class: number; tool: number; method: ErasureMethod }[],
) {
  return api<LotErasureToolRow[]>(`${BASE}/lots/${lotId}/erasure-tools/`, {
    method: 'PUT',
    body: JSON.stringify({ definitions }),
  })
}

/** Filters: `status`, `asset`, `mine`. */
export function listReports(params: ListParams) {
  return api<Paginated<ReportSummary>>(`${BASE}/inspections/` + listQuery(params))
}

export function getReport(id: number) {
  return api<InspectionReport>(`${BASE}/inspections/${id}/`)
}

export function startInspection(assetCode: string, benchCode: string) {
  return api<InspectionReport>(`${BASE}/inspections/start/`, {
    method: 'POST',
    body: JSON.stringify({ asset_code: assetCode, bench_code: benchCode }),
  })
}

export function updateReport(id: number, data: ReportDraft) {
  return api<InspectionReport>(`${BASE}/inspections/${id}/`, {
    method: 'PATCH',
    body: JSON.stringify(data),
  })
}

const reportAction = (id: number, action: string, data: object = {}) =>
  api<InspectionReport>(`${BASE}/inspections/${id}/${action}/`, {
    method: 'POST',
    body: JSON.stringify(data),
  })

export const completeSerial = (id: number, serial: string) => reportAction(id, 'serial', { serial })
export const setReportSpecs = (id: number, specs: Record<string, string>) =>
  reportAction(id, 'specs', { specs })
export const submitReport = (id: number) => reportAction(id, 'submit')
export const returnReport = (id: number, notes: string) => reportAction(id, 'return', { notes })
export const approveReport = (id: number) => reportAction(id, 'approve')
export const markReportSent = (id: number) => reportAction(id, 'sent')
export const addFinding = (
  id: number,
  data: { kind: FindingKind; block_type: string; description: string },
) => reportAction(id, 'findings', data)

export function updateFinding(
  reportId: number,
  findingId: number,
  data: Partial<Pick<Finding, 'kind' | 'block_type' | 'description'>> & {
    value?: string | null
    value_justification?: string
  },
) {
  return api<InspectionReport>(`${BASE}/inspections/${reportId}/findings/${findingId}/`, {
    method: 'PATCH',
    body: JSON.stringify(data),
  })
}

export function deleteFinding(reportId: number, findingId: number) {
  return api<InspectionReport>(`${BASE}/inspections/${reportId}/findings/${findingId}/`, {
    method: 'DELETE',
  })
}

export function uploadReportPhoto(reportId: number, kind: PhotoKind, file: File, description = '') {
  const body = new FormData()
  body.append('file', file)
  body.append('kind', kind)
  body.append('description', description)
  return api<ReportPhoto[]>(`${BASE}/inspections/${reportId}/photos/`, { method: 'POST', body })
}

export function deleteReportPhoto(reportId: number, photoId: number) {
  return api<void>(`${BASE}/inspections/${reportId}/photos/${photoId}/`, { method: 'DELETE' })
}

export function reportPhotoUrl(reportId: number, photoId: number) {
  return `/api${BASE}/inspections/${reportId}/photos/${photoId}/file/`
}

export function addCertificate(
  reportId: number,
  data: {
    result: 'success' | 'failure'
    disk_serial: string
    file?: File | null
    disk_model?: number | null
  },
) {
  const body = new FormData()
  body.append('result', data.result)
  body.append('disk_serial', data.disk_serial)
  if (data.file) body.append('file', data.file)
  if (data.disk_model) body.append('disk_model', String(data.disk_model))
  return api<InspectionReport>(`${BASE}/inspections/${reportId}/certificates/`, {
    method: 'POST',
    body,
  })
}

export function certificateUrl(reportId: number, certificateId: number) {
  return `/api${BASE}/inspections/${reportId}/certificates/${certificateId}/file/?inline=1`
}

export function assetReports(assetId: number) {
  return api<ReportSummary[]>(`${BASE}/assets/${assetId}/reports/`)
}

export function newReportVersion(assetId: number, reason: string) {
  return api<{ id: number }>(`${BASE}/assets/${assetId}/new-report/`, {
    method: 'POST',
    body: JSON.stringify({ reason }),
  })
}

export function disassemble(
  assetId: number,
  parts: { asset_model: number; quantity: number; serial: string }[],
  reason: string,
) {
  return api<Asset[]>(`${BASE}/assets/${assetId}/disassemble/`, {
    method: 'POST',
    body: JSON.stringify({ parts, reason }),
  })
}
