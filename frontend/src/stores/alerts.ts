import { ref } from 'vue'
import { defineStore } from 'pinia'
import {
  alertCount,
  listAlerts,
  readAlert,
  readAllAlerts,
  type Alert,
} from '@/modules/inventory/api'

/**
 * The user's notifications as they happen: the unread count (the top bar's bell and the side
 * menu) and, when new ones arrive, the newest (`arrived`: AlertsMenu pops it up). Checked
 * every few seconds and when the window comes back into view (AlertsMenu).
 */
export const useAlertsStore = defineStore('alerts', () => {
  const unread = ref(0)
  /** The newest notification that arrived since the last check (shown once) */
  const arrived = ref<Alert | null>(null)
  /** Unread ones already known: the first check only learns them (nothing pops up) */
  let seen: Set<number> | null = null

  async function refreshCount() {
    const before = unread.value
    try {
      unread.value = (await alertCount()).unread
    } catch {
      return
    }
    if (seen === null || unread.value > before) await checkNew()
  }

  async function checkNew() {
    try {
      const page = await listAlerts(true)
      const fresh = seen ? page.results.filter((alert) => !seen!.has(alert.id)) : []
      seen = new Set([...(seen ?? []), ...page.results.map((alert) => alert.id)])
      // Newest first (the API's order)
      if (fresh.length) arrived.value = fresh[0]!
    } catch {
      /* the next check tries again */
    }
  }

  async function markRead(id: number) {
    await readAlert(id).catch(() => undefined)
    await refreshCount()
  }

  async function markAllRead() {
    await readAllAlerts().catch(() => undefined)
    await refreshCount()
  }

  return { unread, arrived, refreshCount, markRead, markAllRead }
})
