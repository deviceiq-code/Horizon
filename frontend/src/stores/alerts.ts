import { ref } from 'vue'
import { defineStore } from 'pinia'
import { alertCount, readAlert, readAllAlerts } from '@/modules/inventory/api'

/** Unread alerts: the top bar's bell and the Notifications page share the count. */
export const useAlertsStore = defineStore('alerts', () => {
  const unread = ref(0)

  async function refreshCount() {
    try {
      unread.value = (await alertCount()).unread
    } catch {
      unread.value = 0
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

  return { unread, refreshCount, markRead, markAllRead }
})
