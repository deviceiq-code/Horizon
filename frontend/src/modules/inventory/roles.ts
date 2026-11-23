/**
 * The inventory's roles as the interface uses them (the server checks them again): which
 * actions to offer. Administrators may do everything.
 */
import { computed } from 'vue'
import { useAuthStore } from '@/stores/auth'

export const RECEIVER = 'receiver'
export const STOREKEEPER = 'storekeeper'
export const SUPERVISOR = 'inventory_supervisor'
export const ANALYST = 'remarketing_analyst'
export const COMMERCIAL = 'commercial_finance'

export function useInventoryRoles() {
  const auth = useAuthStore()
  const keys = computed(() => new Set((auth.user?.role_refs ?? []).map((role) => role.key)))
  const has = (...wanted: string[]) =>
    !!auth.user?.is_admin || wanted.some((key) => keys.value.has(key))
  return {
    /** Schedule receivings and shipments, prepare expected lists */
    canSchedule: computed(() => has(ANALYST, SUPERVISOR)),
    /** See expected lists — never the receivers who count (blind count) */
    canSeeExpected: computed(() => has(ANALYST, SUPERVISOR, COMMERCIAL)),
    /** Open lots, triage, register and resolve occurrences, close */
    canReceive: computed(() => has(RECEIVER, SUPERVISOR)),
    /** Accept occurrences */
    isSupervisor: computed(() => has(SUPERVISOR)),
  }
}
