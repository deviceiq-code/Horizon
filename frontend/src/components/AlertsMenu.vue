<script setup lang="ts">
/**
 * The top bar's notifications (the user's own alerts: deadlines near or past, disputes
 * escalated, assets aging in a status…, created by the inventory's daily routine).
 * The bell shows how many are unread (checked every few minutes); opening one goes to its page;
 * "View All Notifications" opens the Notifications page.
 */
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { alertTarget } from '@/alerts'
import NotificationItem from '@/components/NotificationItem.vue'
import NotificationsEmpty from '@/components/NotificationsEmpty.vue'
import { listAlerts, type Alert } from '@/modules/inventory/api'
import { useAlertsStore } from '@/stores/alerts'

const router = useRouter()
const store = useAlertsStore()

const alerts = ref<Alert[]>([])
const open = ref(false)
let timer: ReturnType<typeof setInterval> | undefined

// As they happen: checked every few seconds, and at once when the window comes back into view
const CHECK_EVERY_MS = 15_000
function checkWhenVisible() {
  if (document.visibilityState === 'visible') store.refreshCount()
}
onMounted(() => {
  store.refreshCount()
  timer = setInterval(checkWhenVisible, CHECK_EVERY_MS)
  document.addEventListener('visibilitychange', checkWhenVisible)
  window.addEventListener('focus', checkWhenVisible)
})
onBeforeUnmount(() => {
  clearInterval(timer)
  document.removeEventListener('visibilitychange', checkWhenVisible)
  window.removeEventListener('focus', checkWhenVisible)
})

// A new one pops up on its own (top right); a click opens it
const toast = ref<Alert | null>(null)
const toastOpen = ref(false)
watch(
  () => store.arrived,
  (alert) => {
    if (!alert) return
    toast.value = alert
    toastOpen.value = true
    store.arrived = null
    // The open menu shows it too
    if (open.value) load()
  },
)
function openToast() {
  toastOpen.value = false
  if (toast.value) openAlert(toast.value)
}

async function load() {
  try {
    alerts.value = (await listAlerts()).results
  } catch {
    alerts.value = []
  }
}

async function openAlert(alert: Alert) {
  if (!alert.read) await store.markRead(alert.id)
  open.value = false
  const target = alertTarget(alert)
  if (target) router.push(target)
}

async function readAll() {
  await store.markAllRead()
  await load()
}

function viewAll() {
  open.value = false
  router.push({ name: 'notifications' })
}
</script>

<template>
  <v-menu
    v-model="open"
    location="bottom end"
    offset="8"
    :close-on-content-click="false"
    @update:model-value="$event && load()"
  >
    <template #activator="{ props: menu }">
      <!-- The count outside the button (a button clips what goes past its edges) -->
      <v-badge
        :content="store.unread"
        :model-value="store.unread > 0"
        color="error"
        max="99"
        offset-x="4"
        offset-y="4"
        class="bell-badge"
        data-testid="notifications-count"
      >
        <v-btn
          v-bind="menu"
          icon="mdi-bell-outline"
          variant="text"
          size="small"
          class="bar-icon"
          :title="$t('menu.notifications')"
          :aria-label="$t('menu.notifications')"
          data-testid="notifications"
        />
      </v-badge>
    </template>
    <v-card width="400" max-width="calc(100vw - 24px)" data-testid="alerts-menu">
      <!-- Title, how many are unread; mark them all read -->
      <div class="d-flex align-center pl-6 pr-4 py-4">
        <div class="flex-grow-1">
          <div class="text-h6 font-weight-bold">{{ $t('menu.notifications') }}</div>
          <div class="text-body-2 text-medium-emphasis" data-testid="unread-summary">
            {{ $t('notifications.unreadCount', store.unread) }}
          </div>
        </div>
        <v-btn
          icon="mdi-check-all"
          variant="text"
          size="small"
          :disabled="!store.unread"
          :title="$t('notifications.markAllRead')"
          :aria-label="$t('notifications.markAllRead')"
          data-testid="read-all"
          @click="readAll"
        />
      </div>
      <v-divider />
      <div class="menu-list">
        <NotificationItem
          v-for="alert in alerts"
          :key="alert.id"
          :alert="alert"
          @open="openAlert(alert)"
        />
        <NotificationsEmpty v-if="!alerts.length" />
      </div>
      <v-divider />
      <v-btn
        block
        variant="text"
        size="large"
        class="text-none font-weight-medium"
        rounded="0"
        data-testid="view-all"
        @click="viewAll"
      >
        {{ $t('notifications.viewAll') }}
      </v-btn>
    </v-card>
  </v-menu>

  <!-- A notification that just arrived -->
  <v-snackbar
    v-model="toastOpen"
    location="top right"
    :timeout="8000"
    color="surface"
    elevation="8"
    rounded="lg"
    class="notification-toast"
    content-class="pa-0"
    data-testid="notification-toast"
  >
    <NotificationItem v-if="toast" :alert="toast" @open="openToast" />
    <template #actions>
      <v-btn
        icon="mdi-close"
        size="small"
        variant="text"
        :aria-label="$t('common.close')"
        @click="toastOpen = false"
      />
    </template>
  </v-snackbar>
</template>

<style scoped>
/* As the top bar's other icons (MainLayout's .bar-icon: its scoped style does not reach here) */
.bar-icon {
  color: rgba(var(--v-theme-on-background), 0.78);
}
.bar-icon :deep(.v-icon) {
  font-size: 22px;
}
/* The pop-up: a notification as in the menu */
.notification-toast :deep(.v-snackbar__content) {
  padding: 0;
  min-width: 360px;
  max-width: 420px;
}
/* The count: small, bold, readable over the bar */
.bell-badge :deep(.v-badge__badge) {
  font-size: 0.6875rem;
  font-weight: 700;
  min-width: 18px;
  height: 18px;
  padding: 0 4px;
  pointer-events: none;
}
.menu-list {
  max-height: 440px;
  overflow-y: auto;
}
</style>
