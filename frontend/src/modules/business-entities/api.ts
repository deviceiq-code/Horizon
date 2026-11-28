/**
 * Business Entities (docs/business-entities.md): every company or person Horizon deals with.
 * What they have in common is the entity's; each kind of relationship is a role of it, with
 * its own "active" and data (a customer's contract types — renter, lessee… — are its own). Written together: one key per role — an object turns it on (or
 * changes it), null removes it, absent leaves it as it is.
 */
import { api, listQuery, type ListParams, type Paginated } from '@/api'
import type { AccountManagerRef } from '@/modules/account-managers/api'
import type { ServiceKind } from '@/modules/service-providers/api'

/** The roles, in the page's tabs order (backend `entities.models.EntityRole`) */
export const ENTITY_ROLES = ['customer', 'supplier', 'service_provider', 'buyer'] as const
export type EntityRole = (typeof ENTITY_ROLES)[number]

export const ROLE_ICONS: Record<EntityRole, string> = {
  customer: 'mdi-account-tie-outline',
  supplier: 'mdi-package-variant',
  service_provider: 'mdi-account-hard-hat-outline',
  buyer: 'mdi-cart-outline',
}

/** How a customer takes Horizon's assets or services ("Modalidades"; backend
 * `customers.models.ContractType`): optional — a prospect has none */
export const CONTRACT_TYPES = ['renter', 'lessee', 'bailee', 'service_customer'] as const
export type ContractType = (typeof CONTRACT_TYPES)[number]

/** What a supplier supplies (backend `entities.models.SupplyKind`) */
export const SUPPLY_KINDS = ['products', 'services'] as const
export type SupplyKind = (typeof SUPPLY_KINDS)[number]

export interface EntityRef {
  id: number
  name: string
  trade_name: string
  tax_id: string
  country: string
}

interface RoleBase {
  id: number
  is_active: boolean
}

export interface CustomerRole extends RoleBase {
  contract_types: ContractType[]
  primary_account_manager: number | null
  primary_account_manager_name: string
  secondary_account_managers: number[]
  secondary_account_managers_detail: AccountManagerRef[]
}

export interface ServiceProviderRole extends RoleBase {
  services: ServiceKind[]
  /** Warehouses it runs (read-only) */
  warehouses_count: number
}

export interface SupplierRole extends RoleBase {
  supplies: SupplyKind[]
}

export interface BusinessEntity {
  id: number
  name: string
  trade_name: string
  /** Uppercase, without punctuation (CNPJ/CPF in Brazil) */
  tax_id: string
  /** ISO 3166-1 alpha-2 */
  country: string
  /** Its head office */
  parent: number | null
  parent_detail: EntityRef | null
  /** The entity at the top of its group (itself when it heads one); null on its own */
  group_detail: EntityRef | null
  branches_count: number
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
  /** The roles it has, in ENTITY_ROLES order */
  roles: EntityRole[]
  customer: CustomerRole | null
  supplier: SupplierRole | null
  service_provider: ServiceProviderRole | null
  buyer: RoleBase | null
  created_at: string
  updated_at: string
}

/** A role as sent: its own fields (no ids nor read-only names) */
export interface RolesInput {
  customer?: {
    is_active: boolean
    contract_types: ContractType[]
    primary_account_manager: number | null
    secondary_account_managers: number[]
  } | null
  supplier?: { is_active: boolean; supplies: SupplyKind[] } | null
  service_provider?: { is_active: boolean; services: ServiceKind[] } | null
  buyer?: { is_active: boolean } | null
}

export type BusinessEntityInput = Pick<
  BusinessEntity,
  | 'name'
  | 'trade_name'
  | 'tax_id'
  | 'country'
  | 'parent'
  | 'contact_name'
  | 'email'
  | 'phone'
  | 'postal_code'
  | 'street'
  | 'number'
  | 'complement'
  | 'district'
  | 'city'
  | 'state'
  | 'is_active'
  | 'notes'
  | 'keywords'
> &
  RolesInput

export type EntityCounts = Record<'all' | EntityRole, number>

const BASE = '/business-entities/'

/** Filters: `role`, `is_active` (in a role: the role's), `name`, `tax_id`, `location`,
 * `contract_type`, `account_manager`, `service`, `supplies`, `parent`, `group`. */
export function listBusinessEntities(params: ListParams) {
  return api<Paginated<BusinessEntity>>(BASE + listQuery(params))
}

export function getBusinessEntity(id: number) {
  return api<BusinessEntity>(`${BASE}${id}/`)
}

export function entityCounts() {
  return api<EntityCounts>(`${BASE}counts/`)
}

/** The likely head office of a Brazilian CNPJ (same root), or null. */
export async function parentSuggestion(country: string, taxId: string, exclude?: number) {
  const query = new URLSearchParams({ country, tax_id: taxId })
  if (exclude) query.set('exclude', String(exclude))
  const body = await api<{ suggestion: EntityRef | null }>(`${BASE}parent-suggestion/?${query}`)
  return body.suggestion
}

export function createBusinessEntity(data: BusinessEntityInput) {
  return api<BusinessEntity>(BASE, { method: 'POST', body: JSON.stringify(data) })
}

export function updateBusinessEntity(id: number, data: Partial<BusinessEntityInput>) {
  return api<BusinessEntity>(`${BASE}${id}/`, { method: 'PATCH', body: JSON.stringify(data) })
}

export function deleteBusinessEntity(id: number) {
  return api<void>(`${BASE}${id}/`, { method: 'DELETE' })
}
