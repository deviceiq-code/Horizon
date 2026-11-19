/** System roles show translated (their stored name and description are in English). */
import type { Role, RoleRef } from './api'

type Translate = (key: string) => string

export function roleName(role: RoleRef, t: Translate): string {
  return role.is_system && role.key ? t(`users.systemRoles.${role.key}.name`) : role.name
}

export function roleDescription(role: Role, t: Translate): string {
  return role.is_system && role.key
    ? t(`users.systemRoles.${role.key}.description`)
    : role.description
}
