import { ref } from 'vue'
import { defineStore } from 'pinia'

export type NotificationColor = 'success' | 'error' | 'info' | 'warning'

/** Global snackbar shown by App.vue — call notify() from any page. */
export const useNotificationsStore = defineStore('notifications', () => {
  const visible = ref(false)
  const text = ref('')
  const color = ref<NotificationColor>('success')

  function notify(message: string, kind: NotificationColor = 'success') {
    text.value = message
    color.value = kind
    visible.value = true
  }

  return { visible, text, color, notify }
})
