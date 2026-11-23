import { api, listQuery, type ListParams, type Paginated } from '@/api'

export interface RoleRef {
  id: number
  /** Stable identifier of system roles ("administrator"); "" for the others */
  key: string
  name: string
  is_system: boolean
}

export interface Role extends RoleRef {
  description: string
  keywords: string[]
  users_count: number
  created_at: string
}

export type RoleInput = Pick<Role, 'name' | 'description' | 'keywords'>

export interface User {
  id: number
  username: string
  first_name: string
  last_name: string
  full_name: string
  email: string
  is_active: boolean
  /** Role ids */
  roles: number[]
  /** Same roles for display, sorted by name (read-only) */
  roles_detail: RoleRef[]
  /** Changes with every new photo; null without one (see userPhotoUrl) */
  photo_version: string | null
  /** False for users without a password yet (e.g. former account managers): cannot sign in */
  has_password: boolean
  // Employee data
  id_document_type: IdDocumentType | ''
  /** Letters and digits only (e.g. CPF "52998224725") */
  id_document_number: string
  employee_number: string
  /** ISO 3166-1 alpha-2 */
  nationality: string
  /** YYYY-MM-DD */
  birth_date: string | null
  job_title: string
  department: string
  work_location: string
  /** Manager's user id */
  manager: number | null
  manager_name: string | null
  hire_date: string | null
  phone: string
  mobile_phone: string
  /** Business verticals an account manager works in (only with the Account Manager role) */
  verticals: number[]
  verticals_detail: { id: number; name: string; is_enabled: boolean }[]
  keywords: string[]
  last_login: string | null
  date_joined: string
}

export const ID_DOCUMENT_TYPES = ['cpf', 'rg', 'national_id', 'passport', 'other'] as const
export type IdDocumentType = (typeof ID_DOCUMENT_TYPES)[number]

/** Key of the system role that lets a user be a customer's account manager. */
export const ACCOUNT_MANAGER_ROLE = 'account_manager'

export const EMPLOYEE_FIELDS = [
  'id_document_type',
  'id_document_number',
  'employee_number',
  'nationality',
  'birth_date',
  'job_title',
  'department',
  'work_location',
  'manager',
  'hire_date',
  'phone',
  'mobile_phone',
  'verticals',
  'keywords',
] as const

export type UserInput = Pick<
  User,
  | 'username'
  | 'first_name'
  | 'last_name'
  | 'email'
  | 'is_active'
  | 'roles'
  | (typeof EMPLOYEE_FIELDS)[number]
> & {
  /** Required when creating; when editing, empty keeps the current password */
  password?: string
}

const USERS = '/users/'
const ROLES = '/roles/'

export function listUsers(params: ListParams) {
  return api<Paginated<User>>(USERS + listQuery(params))
}

export function createUser(data: UserInput) {
  return api<User>(USERS, { method: 'POST', body: JSON.stringify(data) })
}

export function updateUser(id: number, data: Partial<UserInput>) {
  return api<User>(`${USERS}${id}/`, { method: 'PATCH', body: JSON.stringify(data) })
}

export function deleteUser(id: number) {
  return api<void>(`${USERS}${id}/`, { method: 'DELETE' })
}

export function listRoles(params: ListParams) {
  return api<Paginated<Role>>(ROLES + listQuery(params))
}

/** Every role, by name (there are few), e.g. to choose a user's roles. */
export async function allRoles() {
  return (await listRoles({ page: 1, pageSize: 200, ordering: 'name' })).results
}

export function createRole(data: RoleInput) {
  return api<Role>(ROLES, { method: 'POST', body: JSON.stringify(data) })
}

export function updateRole(id: number, data: RoleInput) {
  return api<Role>(`${ROLES}${id}/`, { method: 'PATCH', body: JSON.stringify(data) })
}

export function deleteRole(id: number) {
  return api<void>(`${ROLES}${id}/`, { method: 'DELETE' })
}

/** A user's photo (anyone signed in can see it); the version refreshes it after a change. */
export function userPhotoUrl(id: number, version: string) {
  return `/api${USERS}${id}/photo/?v=${version}`
}

/** Sets or replaces the photo (send a square picture: utils/image.squareImage). */
export function uploadUserPhoto(id: number, file: File) {
  const body = new FormData()
  body.append('file', file)
  return api<User>(`${USERS}${id}/photo/`, { method: 'POST', body })
}

export function deleteUserPhoto(id: number) {
  return api<void>(`${USERS}${id}/photo/`, { method: 'DELETE' })
}
