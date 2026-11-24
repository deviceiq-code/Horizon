<script setup lang="ts">
/**
 * The top bar's notifications: alerts for the user or their roles (deadlines near or past,
 * disputes escalated, assets aging in a status…), created by the inventory's daily routine.
 * The bell shows how many are unread (checked every few minutes); opening one goes to its page.
 */
import { onBeforeUnmount, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'
import { useDateFormat } from '@/composables/useDateFormat'
import {
  alertCount,
  listAlerts,
  readAlert,
  readAllAlerts,
  type Alert,
} from '@/modules/inventory/api'

const { t } = useI18n()
const { d } = useDateFormat()
const router = useRouter()

const unread = ref(0)
const alerts = ref<Alert[]>([])
const open = ref(false)
let timer: ReturnType<typeof setInterval> | undefined

async function refreshCount() {
  try {
    unread.value = (await alertCount()).unread
  } catch {
    unread.value = 0
  }
}

onMounted(() => {
  refreshCount()
  timer = setInterval(refreshCount, 3 * 60_000)
})
onBeforeUnmount(() => clearInterval(timer))

async function load() {
  try {
    alerts.value = (await listAlerts()).results
  } catch {
    alerts.value = []
  }
}

function text(alert: Alert): string {
  const params = { ...alert.params }
  if (typeof params.status === 'string') params.status = t(`inventory.statuses.${params.status}`)
  return t(`inventory.alerts.kinds.${alert.kind}`, params)
}

const TARGETS: Record<string, string> = {
  block: 'inventory-blocks',
  dispute: 'inventory-disputes',
  asset: 'inventory-assets',
}

async function openAlert(alert: Alert) {
  if (!alert.read) {
    await readAlert(alert.id).catch(() => undefined)
    await refreshCount()
  }
  open.value = false
  const target = TARGETS[alert.ref.split(':')[0] ?? '']
  if (target) router.push({ name: target })
}

async function readAll() {
  await readAllAlerts().catch(() => undefined)
  await Promise.all([load(), refreshCount()])
}
</script>

<template>
  <v-menu
    v-model="open"
    location="bottom end"
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
        <v-badge :content="unread" :model-value="unread > 0" color="error" floating>
          <v-icon icon="mdi-bell-outline" />
        </v-badge>
      </v-btn>
    </template>
    <v-card min-width="360" max-width="420" data-testid="alerts-menu">
      <div class="d-flex align-center px-4 pt-3">
        <div class="text-subtitle-1 font-weight-medium flex-grow-1">
          {{ $t('menu.notifications') }}
        </div>
        <v-btn v-if="unread" size="small" variant="text" @click="readAll">{{
          $t('inventory.alerts.readAll')
        }}</v-btn>
      </div>
      <v-list density="compact" max-height="420" class="overflow-y-auto">
        <v-list-item
          v-for="alert in alerts"
          :key="alert.id"
          :class="{ 'font-weight-medium': !alert.read }"
          data-testid="alert"
          @click="openAlert(alert)"
        >
          <template #prepend>
            <v-icon
              :icon="alert.read ? 'mdi-bell-outline' : 'mdi-bell-ring-outline'"
              :color="alert.read ? undefined : 'primary'"
            />
          </template>
          <v-list-item-title class="text-wrap">{{ text(alert) }}</v-list-item-title>
          <v-list-item-subtitle>{{
            d(new Date(alert.created_at), 'dateTime')
          }}</v-list-item-subtitle>
        </v-list-item>
        <v-list-item v-if="!alerts.length" class="text-medium-emphasis">{{
          $t('inventory.alerts.empty')
        }}</v-list-item>
      </v-list>
    </v-card>
  </v-menu>
</template>
