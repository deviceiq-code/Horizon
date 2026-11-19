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
  users_count: number
  created_at: string
}

export type RoleInput = Pick<Role, 'name' | 'description'>

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
  last_login: string | null
  date_joined: string
}

export type UserInput = Pick<
  User,
  'username' | 'first_name' | 'last_name' | 'email' | 'is_active' | 'roles'
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
