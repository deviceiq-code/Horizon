<script setup lang="ts">
/**
 * The top bar's notifications (the user's own alerts: deadlines near or past, disputes
 * escalated, assets aging in a status…, created by the inventory's daily routine).
 * The bell shows how many are unread (checked every few minutes); opening one goes to its page;
 * "View All Notifications" opens the Notifications page.
 */
import { onBeforeUnmount, onMounted, ref } from 'vue'
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

onMounted(() => {
  store.refreshCount()
  timer = setInterval(store.refreshCount, 3 * 60_000)
})
onBeforeUnmount(() => clearInterval(timer))

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
      <v-btn
        v-bind="menu"
        icon
        variant="text"
        size="small"
        class="bar-icon"
        :title="$t('menu.notifications')"
        :aria-label="$t('menu.notifications')"
        data-testid="notifications"
      >
        <v-badge :content="store.unread" :model-value="store.unread > 0" color="error" floating>
          <v-icon icon="mdi-bell-outline" />
        </v-badge>
      </v-btn>
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
</template>

<style scoped>
.menu-list {
  max-height: 440px;
  overflow-y: auto;
}
</style>
