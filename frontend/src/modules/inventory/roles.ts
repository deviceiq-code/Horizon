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
export const TECHNICIAN = 'inspection_technician'

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
    /** Accept occurrences, approve reports, keep the inventory catalogs */
    isSupervisor: computed(() => has(SUPERVISOR)),
    /** Inspect: reports, photos, findings, erasure certificates, part harvesting */
    canInspect: computed(() => has(TECHNICIAN, SUPERVISOR)),
    /** Mark reports as sent to customers */
    canSend: computed(() => has(COMMERCIAL, SUPERVISOR)),
    /** Disposals: create, reserve assets, values, cancel */
    canDispose: computed(() => has(COMMERCIAL, ANALYST, SUPERVISOR)),
    /** Disposals: pick (read each ID) and ship */
    canPick: computed(() => has(STOREKEEPER, SUPERVISOR)),
    /** Transfers: request, change items, cancel (supervisors approve) */
    canRequestTransfer: computed(() => has(ANALYST, SUPERVISOR)),
    /** Transfers: pick and send at the origin, receive at the destination */
    canHandleTransfer: computed(() => has(STOREKEEPER, RECEIVER, SUPERVISOR)),
  }
}
