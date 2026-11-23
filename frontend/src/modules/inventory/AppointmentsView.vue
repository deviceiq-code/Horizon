<script setup lang="ts">
/**
 * Scheduling of receivings and shipments at the warehouses' docks: a calendar (month, week or
 * day; receivings and shipments in their colors, cancelled ones faded) and a list with filters.
 * Analysts and supervisors schedule; receivers open the lot of a receiving when it arrives.
 */
import { computed, onMounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'
import ServerCrudTable from '@/components/ServerCrudTable.vue'
import { useColumnFilters } from '@/composables/useColumnFilters'
import { useDateFormat } from '@/composables/useDateFormat'
import { listWarehouses, type Warehouse } from '@/modules/warehouses/api'
import AppointmentFormDialog from './AppointmentFormDialog.vue'
import AppointmentStatusChip from './AppointmentStatusChip.vue'
import LotOpenDialog from './LotOpenDialog.vue'
import {
  APPOINTMENT_STATUSES,
  deleteAppointment,
  listAppointments,
  type Appointment,
  type Lot,
} from './api'
import { dayOf, localParts } from './dates'
import { useInventoryRoles } from './roles'

const { t } = useI18n()
const { d } = useDateFormat()
const router = useRouter()
const { canSchedule } = useInventoryRoles()

const view = ref<'calendar' | 'list'>('calendar')
const calendarType = ref<'month' | 'week' | 'day'>('week')
const focus = ref(dayOf(new Date()))
const warehouses = ref<Warehouse[]>([])
const warehouseId = ref<number | null>(null)
const appointments = ref<Appointment[]>([])
const loading = ref(false)
const calendar = ref<{ prev: () => void; next: () => void; title: string } | null>(null)

const warehouseOptions = computed(() => [
  { value: null, title: t('common.filters.all') },
  ...warehouses.value.map((w) => ({ value: w.id, title: `${w.code} · ${w.name}` })),
])

onMounted(async () => {
  try {
    warehouses.value = (await listWarehouses({ page: 1, pageSize: 200, ordering: 'name' })).results
  } catch {
    warehouses.value = []
  }
  await loadCalendar()
})

/** The days the calendar shows, with a margin (a month view starts and ends in other months). */
function range(): { from: string; to: string } {
  const center = new Date(`${focus.value}T12:00`)
  const days = calendarType.value === 'month' ? 40 : calendarType.value === 'week' ? 8 : 1
  const from = new Date(center)
  from.setDate(center.getDate() - days)
  const to = new Date(center)
  to.setDate(center.getDate() + days)
  return { from: dayOf(from), to: dayOf(to) }
}

async function loadCalendar() {
  loading.value = true
  try {
    const { from, to } = range()
    const page = await listAppointments({
      page: 1,
      pageSize: 200,
      ordering: 'starts_at',
      filters: { from, to, ...(warehouseId.value ? { warehouse: warehouseId.value } : {}) },
    })
    appointments.value = page.results
  } catch {
    appointments.value = []
  } finally {
    loading.value = false
  }
}
watch([focus, calendarType, warehouseId], loadCalendar)

const events = computed(() =>
  appointments.value.map((a) => ({
    name: `${a.code} · ${a.customer_name ?? t(`inventory.appointments.kinds.${a.kind}`)}`,
    start: new Date(a.starts_at),
    end: new Date(a.ends_at),
    timed: true,
    color: ['cancelled', 'no_show'].includes(a.status)
      ? 'grey'
      : a.kind === 'receiving'
        ? 'primary'
        : 'secondary',
    appointment: a,
  })),
)

// --- List --------------------------------------------------------------------------------------

const table = ref<{ reload: () => Promise<void> } | null>(null)
const { filters, clear: clearFilters } = useColumnFilters(['kind', 'status'] as const, [])
const kindOptions = computed(() =>
  (['receiving', 'shipping'] as const).map((value) => ({
    value,
    title: t(`inventory.appointments.kinds.${value}`),
  })),
)
const statusOptions = computed(() =>
  APPOINTMENT_STATUSES.map((value) => ({
    value,
    title: t(`inventory.appointments.statuses.${value}`),
  })),
)
const headers = computed(() => [
  { title: t('inventory.appointments.code'), key: 'code', sortable: false, width: 150 },
  { title: t('inventory.appointments.kind'), key: 'kind', width: 160 },
  { title: t('inventory.appointments.when'), key: 'starts_at', width: 220 },
  { title: t('inventory.fields.warehouse'), key: 'warehouse', sortable: false, width: 120 },
  { title: t('inventory.appointments.customer'), key: 'customer_name', sortable: false },
  { title: t('inventory.fields.status'), key: 'status', width: 160 },
])

// --- Dialogs -----------------------------------------------------------------------------------

const formOpen = ref(false)
const shownId = ref<number | null>(null)
const newDate = ref<string | null>(null)

function openAppointment(id: number | null, day: string | null = null) {
  shownId.value = id
  newDate.value = day
  formOpen.value = true
}

function onSaved() {
  loadCalendar()
  table.value?.reload()
}

const lotOpen = ref(false)
const lotAppointment = ref<Appointment | null>(null)

function startReceiving(appointment: Appointment) {
  formOpen.value = false
  lotAppointment.value = appointment
  lotOpen.value = true
}

function onLotOpened(lot: Lot) {
  router.push({ name: 'inventory-lot', params: { id: lot.id } })
}

function timeRange(a: Appointment): string {
  return `${localParts(a.starts_at).time}–${localParts(a.ends_at).time}`
}
</script>

<template>
  <v-container fluid class="module-page">
    <h1 class="mb-1">{{ $t('inventory.appointments.title') }}</h1>
    <p class="text-medium-emphasis mb-4">{{ $t('inventory.appointments.subtitle') }}</p>

    <div class="d-flex flex-wrap align-center ga-3 mb-4">
      <v-btn-toggle v-model="view" mandatory density="compact" variant="outlined" divided>
        <v-btn
          value="calendar"
          prepend-icon="mdi-calendar-month-outline"
          data-testid="view-calendar"
        >
          {{ $t('inventory.appointments.calendar') }}
        </v-btn>
        <v-btn value="list" prepend-icon="mdi-format-list-bulleted" data-testid="view-list">
          {{ $t('inventory.appointments.list') }}
        </v-btn>
      </v-btn-toggle>
      <v-select
        v-if="view === 'calendar'"
        v-model="warehouseId"
        :items="warehouseOptions"
        :label="$t('inventory.fields.warehouse')"
        density="compact"
        hide-details
        style="max-width: 280px"
      />
      <v-spacer />
      <v-btn
        v-if="canSchedule"
        color="primary"
        prepend-icon="mdi-plus"
        data-testid="new-appointment"
        @click="openAppointment(null, focus)"
      >
        {{ $t('inventory.appointments.new') }}
      </v-btn>
    </div>

    <v-card v-if="view === 'calendar'" :loading="loading" class="pa-2">
      <div class="d-flex flex-wrap align-center ga-2 mb-2 px-2">
        <v-btn icon="mdi-chevron-left" variant="text" size="small" @click="calendar?.prev()" />
        <v-btn variant="tonal" size="small" @click="focus = dayOf(new Date())">
          {{ $t('inventory.appointments.today') }}
        </v-btn>
        <v-btn icon="mdi-chevron-right" variant="text" size="small" @click="calendar?.next()" />
        <span class="text-subtitle-1 font-weight-medium ml-2">{{ calendar?.title }}</span>
        <v-spacer />
        <v-btn-toggle v-model="calendarType" mandatory density="compact" variant="text">
          <v-btn value="month">{{ $t('inventory.appointments.month') }}</v-btn>
          <v-btn value="week">{{ $t('inventory.appointments.week') }}</v-btn>
          <v-btn value="day">{{ $t('inventory.appointments.day') }}</v-btn>
        </v-btn-toggle>
      </div>
      <v-calendar
        ref="calendar"
        v-model="focus"
        :type="calendarType"
        :events="events"
        :first-interval="6"
        :interval-count="15"
        event-overlap-mode="column"
        data-testid="calendar"
        @click:date="
          (_e: unknown, day: { date: string }) => {
            focus = day.date
            calendarType = 'day'
          }
        "
      >
        <template #event="{ event }">
          <div
            class="px-1 text-truncate appointment-event"
            :title="(event as { name: string }).name"
            data-testid="calendar-event"
            @click.stop="openAppointment((event as { appointment: Appointment }).appointment.id)"
          >
            <strong>{{ timeRange((event as { appointment: Appointment }).appointment) }}</strong>
            {{ (event as { name: string }).name }}
          </div>
        </template>
      </v-calendar>
      <div class="d-flex ga-4 px-2 pt-2 text-caption">
        <span class="d-flex align-center ga-1">
          <v-icon icon="mdi-square-rounded" color="primary" size="14" />
          {{ $t('inventory.appointments.kinds.receiving') }}
        </span>
        <span class="d-flex align-center ga-1">
          <v-icon icon="mdi-square-rounded" color="secondary" size="14" />
          {{ $t('inventory.appointments.kinds.shipping') }}
        </span>
      </div>
    </v-card>

    <ServerCrudTable
      v-else
      ref="table"
      :fetch-page="listAppointments"
      :delete-item="deleteAppointment"
      :headers="headers"
      :sort-by="[{ key: 'starts_at', order: 'desc' }]"
      :search-placeholder="$t('inventory.appointments.searchPlaceholder')"
      :filters="filters"
      filters-storage-key="inventory-appointments"
      :empty-text="$t('inventory.appointments.empty')"
      :no-results-text="$t('inventory.appointments.noResults')"
      :delete-title="$t('inventory.appointments.deleteTitle')"
      :delete-message="
        (a: Appointment) => $t('inventory.appointments.deleteConfirm', { code: a.code })
      "
      :deleted-text="$t('inventory.appointments.deleted')"
      hide-create
      :can-delete="(a: Appointment) => canSchedule && !a.lot"
      edit-icon="mdi-open-in-new"
      :edit-title="$t('inventory.appointments.open')"
      @clear-filters="clearFilters"
      @edit="(a: Appointment) => openAppointment(a.id)"
    >
      <template #[`filter.kind`]>
        <v-select
          v-model="filters.kind"
          :items="kindOptions"
          :placeholder="$t('common.filters.all')"
          density="compact"
          hide-details
          clearable
        />
      </template>
      <template #[`filter.status`]>
        <v-select
          v-model="filters.status"
          :items="statusOptions"
          :placeholder="$t('common.filters.all')"
          density="compact"
          hide-details
          clearable
        />
      </template>
      <template #[`item.code`]="{ item }">
        <span class="font-weight-medium">{{ item.code }}</span>
        <v-icon
          v-if="item.conflicts.length"
          icon="mdi-alert-outline"
          color="warning"
          size="16"
          class="ml-1"
          :title="$t('inventory.appointments.conflicts', { codes: item.conflicts.join(', ') })"
        />
      </template>
      <template #[`item.kind`]="{ item }">
        {{ $t(`inventory.appointments.kinds.${item.kind}`) }}
      </template>
      <template #[`item.starts_at`]="{ item }">
        {{ d(new Date(item.starts_at), 'short') }} · {{ timeRange(item) }}
      </template>
      <template #[`item.warehouse`]="{ item }">
        <span :title="item.warehouse_detail.name">{{ item.warehouse_detail.code }}</span>
      </template>
      <template #[`item.customer_name`]="{ item }">{{ item.customer_name ?? '—' }}</template>
      <template #[`item.status`]="{ item }">
        <AppointmentStatusChip :status="item.status" />
      </template>
    </ServerCrudTable>

    <AppointmentFormDialog
      v-model="formOpen"
      :appointment-id="shownId"
      :start-date="newDate"
      @saved="onSaved"
      @open-lot="startReceiving"
    />
    <LotOpenDialog v-model="lotOpen" :appointment="lotAppointment" @opened="onLotOpened" />
  </v-container>
</template>

<style scoped>
.appointment-event {
  font-size: 0.75rem;
  line-height: 1.3;
  cursor: pointer;
  height: 100%;
}
</style>
