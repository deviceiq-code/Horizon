<script setup lang="ts">
/**
 * Notifications: the user's own alerts (every user has theirs), All or Unread, grouped Today /
 * Yesterday / Earlier; opening one marks it read and goes to its page; "Mark All as Read".
 */
import { computed, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { alertTarget, groupByDay } from '@/alerts'
import NotificationItem from '@/components/NotificationItem.vue'
import NotificationsEmpty from '@/components/NotificationsEmpty.vue'
import { listAlerts, type Alert } from '@/modules/inventory/api'
import { useAlertsStore } from '@/stores/alerts'

const router = useRouter()
const store = useAlertsStore()

const tab = ref<'all' | 'unread'>('all')
const alerts = ref<Alert[]>([])
const page = ref(1)
const hasMore = ref(false)
const loading = ref(false)
const failed = ref(false)

async function load(more = false) {
  loading.value = true
  failed.value = false
  try {
    page.value = more ? page.value + 1 : 1
    const data = await listAlerts(tab.value === 'unread', page.value)
    alerts.value = more ? [...alerts.value, ...data.results] : data.results
    hasMore.value = !!data.next
  } catch {
    failed.value = true
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  load()
  store.refreshCount()
})
watch(tab, () => load())

const groups = computed(() => groupByDay(alerts.value))

async function openAlert(alert: Alert) {
  if (!alert.read) {
    await store.markRead(alert.id)
    alert.read = true
  }
  const target = alertTarget(alert)
  if (target) router.push(target)
}

async function readAll() {
  await store.markAllRead()
  await load()
}
</script>

<template>
  <v-container fluid class="module-page">
    <div class="d-flex align-start flex-wrap ga-4 mb-4">
      <div class="flex-grow-1">
        <h1 class="mb-1">{{ $t('menu.notifications') }}</h1>
        <p class="text-medium-emphasis mb-0">{{ $t('notifications.subtitle') }}</p>
      </div>
      <v-btn
        variant="text"
        color="primary"
        prepend-icon="mdi-check-all"
        :disabled="!store.unread"
        data-testid="read-all"
        @click="readAll"
      >
        {{ $t('notifications.markAllRead') }}
      </v-btn>
    </div>

    <v-tabs v-model="tab" color="primary" class="mb-4" data-testid="notification-tabs">
      <v-tab value="all" data-testid="tab-all">{{ $t('notifications.all') }}</v-tab>
      <v-tab value="unread" data-testid="tab-unread">
        {{ $t('notifications.unread', { n: store.unread }) }}
      </v-tab>
    </v-tabs>

    <v-card>
      <v-progress-linear v-if="loading && !alerts.length" indeterminate color="primary" />
      <v-alert v-if="failed" type="error" variant="tonal" class="ma-4">
        {{ $t('common.loadError') }}
        <template #append>
          <v-btn variant="text" size="small" @click="load()">{{ $t('common.retry') }}</v-btn>
        </template>
      </v-alert>

      <!-- Nothing: all caught up -->
      <NotificationsEmpty v-else-if="!loading && !alerts.length" />

      <template v-for="(group, index) in groups" :key="group.group">
        <v-divider v-if="index" />
        <div class="group-title" :data-testid="`group-${group.group}`">
          {{ $t(`notifications.groups.${group.group}`) }}
        </div>
        <template v-for="(alert, position) in group.alerts" :key="alert.id">
          <v-divider v-if="position" class="mx-5" />
          <NotificationItem :alert="alert" @open="openAlert(alert)" />
        </template>
      </template>

      <div v-if="hasMore" class="text-center pa-3">
        <v-btn variant="text" :loading="loading" data-testid="load-more" @click="load(true)">
          {{ $t('notifications.loadMore') }}
        </v-btn>
      </div>
    </v-card>
  </v-container>
</template>

<style scoped>
.group-title {
  padding: 16px 20px 4px;
  font-size: 0.75rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: rgba(var(--v-theme-on-surface), var(--v-medium-emphasis-opacity));
}
</style>
