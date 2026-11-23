<script setup lang="ts">
/**
 * Create or edit a receiving or shipping appointment: warehouse, customer, day and time
 * window, carrier and vehicle; a receiving also has its expected list (tab "Expected List",
 * only for those who may see it — never the receivers who count). Status actions in the
 * footer: confirm, cancel, no-show, reschedule; a receiving starts with its lot.
 */
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { ApiError, deleteErrorMessage } from '@/api'
import FormDialog from '@/components/FormDialog.vue'
import ServiceProviderPicker from '@/modules/service-providers/ServiceProviderPicker.vue'
import { listWarehouses, type Warehouse } from '@/modules/warehouses/api'
import { useNotificationsStore } from '@/stores/notifications'
import AppointmentStatusChip from './AppointmentStatusChip.vue'
import CustomerSelect from './CustomerSelect.vue'
import ExpectedItemsEditor from './ExpectedItemsEditor.vue'
import {
  createAppointment,
  deleteAppointment,
  getAppointment,
  setAppointmentStatus,
  updateAppointment,
  type Appointment,
  type AppointmentKind,
  type AppointmentStatus,
} from './api'
import { toInput, toRows, type EditorRow } from './expectedRows'
import { useInventoryRoles } from './roles'
import { localParts, toIso } from './dates'

const props = defineProps<{
  appointmentId: number | null
  /** New appointment: the day clicked on the calendar (YYYY-MM-DD) */
  startDate?: string | null
}>()
const open = defineModel<boolean>({ required: true })
const emit = defineEmits<{ saved: []; openLot: [appointment: Appointment] }>()

const { t } = useI18n()
const notifications = useNotificationsStore()
const { canSchedule, canSeeExpected, canReceive } = useInventoryRoles()

const appointment = ref<Appointment | null>(null)
const warehouses = ref<Warehouse[]>([])
const tab = ref<'details' | 'expected'>('details')
const kind = ref<AppointmentKind>('receiving')
const warehouseId = ref<number | null>(null)
const customer = ref<number | null>(null)
const date = ref('')
const startTime = ref('08:00')
const endTime = ref('10:00')
const carrier = ref<number | null>(null)
const carrierName = ref('')
const plate = ref('')
const driver = ref('')
const volumes = ref('')
const notes = ref('')
const rows = ref<EditorRow[]>([])
const editor = ref<{ invalid: EditorRow[] } | null>(null)
const fieldErrors = ref<Record<string, string[]>>({})
const generalError = ref('')
const saving = ref(false)
const loading = ref(false)
const openCount = ref(0)
const formRef = ref<{ validate: () => Promise<{ valid: boolean }> } | null>(null)

const isEdit = computed(() => props.appointmentId !== null)
const readonly = computed(() => !canSchedule.value || appointment.value?.status === 'done')
const showExpected = computed(() => kind.value === 'receiving' && canSeeExpected.value)
const warehouseOptions = computed(() =>
  warehouses.value.map((w) => ({ value: w.id, title: `${w.code} · ${w.name}` })),
)
const required = [
  (v: unknown) => (v !== null && v !== undefined && v !== '') || t('validation.required'),
]

watch(open, async (isOpen) => {
  if (!isOpen) return
  tab.value = 'details'
  fieldErrors.value = {}
  generalError.value = ''
  appointment.value = null
  openCount.value += 1
  loading.value = true
  try {
    if (!warehouses.value.length) {
      warehouses.value = (
        await listWarehouses({ page: 1, pageSize: 200, ordering: 'name' })
      ).results
    }
    const a = props.appointmentId !== null ? await getAppointment(props.appointmentId) : null
    appointment.value = a
    kind.value = a?.kind ?? 'receiving'
    warehouseId.value = a?.warehouse ?? warehouses.value[0]?.id ?? null
    customer.value = a?.customer ?? null
    const start = a
      ? localParts(a.starts_at)
      : { date: props.startDate ?? localParts(new Date().toISOString()).date, time: '08:00' }
    date.value = start.date
    startTime.value = start.time
    endTime.value = a ? localParts(a.ends_at).time : '10:00'
    carrier.value = a?.carrier ?? null
    carrierName.value = a?.carrier_name ?? ''
    plate.value = a?.vehicle_plate ?? ''
    driver.value = a?.driver_name ?? ''
    volumes.value = a?.expected_volumes != null ? String(a.expected_volumes) : ''
    notes.value = a?.notes ?? ''
    rows.value = toRows(a?.expected_items ?? [])
  } catch {
    generalError.value = t('common.loadError')
  } finally {
    loading.value = false
  }
})

async function submit() {
  const result = await formRef.value?.validate()
  if (!result?.valid) return
  if (showExpected.value && editor.value?.invalid.length) {
    tab.value = 'expected'
    generalError.value = t('inventory.expected.fixRows')
    return
  }
  saving.value = true
  fieldErrors.value = {}
  generalError.value = ''
  try {
    const data = {
      kind: kind.value,
      warehouse: warehouseId.value,
      customer: customer.value,
      starts_at: toIso(date.value, startTime.value),
      ends_at: toIso(date.value, endTime.value),
      carrier: carrier.value,
      carrier_name: carrierName.value,
      vehicle_plate: plate.value,
      driver_name: driver.value,
      expected_volumes: volumes.value ? Number(volumes.value) : null,
      notes: notes.value,
      ...(showExpected.value ? { expected_items: toInput(rows.value) } : {}),
    }
    if (appointment.value) await updateAppointment(appointment.value.id, data)
    else await createAppointment(data)
    notifications.notify(
      t(isEdit.value ? 'inventory.appointments.updated' : 'inventory.appointments.created'),
    )
    emit('saved')
    open.value = false
  } catch (error) {
    const errors = error instanceof ApiError ? error.fieldErrors() : {}
    if (Object.keys(errors).length) {
      fieldErrors.value = errors
      if (errors.expected_items) tab.value = 'expected'
      const detail = (error as ApiError).data as { detail?: string } | null
      if (detail?.detail) generalError.value = detail.detail
    } else {
      generalError.value =
        error instanceof ApiError && error.message ? error.message : t('common.saveError')
    }
  } finally {
    saving.value = false
  }
}

// --- Status --------------------------------------------------------------------------------------

const statusActions = computed(() => {
  const a = appointment.value
  if (!a || !canSchedule.value) return []
  const actions: { status: AppointmentStatus; icon: string }[] = []
  if (a.status === 'scheduled') actions.push({ status: 'confirmed', icon: 'mdi-check' })
  if (a.status === 'scheduled' || a.status === 'confirmed') {
    actions.push({ status: 'no_show', icon: 'mdi-account-off-outline' })
    actions.push({ status: 'cancelled', icon: 'mdi-cancel' })
  }
  if (a.status === 'cancelled' || a.status === 'no_show') {
    actions.push({ status: 'scheduled', icon: 'mdi-calendar-refresh' })
  }
  if (a.kind === 'shipping' && (a.status === 'scheduled' || a.status === 'confirmed')) {
    actions.push({ status: 'in_progress', icon: 'mdi-play' })
  }
  if (a.kind === 'shipping' && a.status === 'in_progress') {
    actions.push({ status: 'done', icon: 'mdi-flag-checkered' })
  }
  return actions
})

async function changeStatus(status: AppointmentStatus) {
  if (!appointment.value) return
  try {
    appointment.value = await setAppointmentStatus(appointment.value.id, status)
    notifications.notify(t(`inventory.appointments.statusChanged.${status}`))
    emit('saved')
  } catch (error) {
    notifications.notify(error instanceof ApiError ? error.message : t('common.saveError'), 'error')
  }
}

const canOpenLot = computed(
  () =>
    canReceive.value &&
    appointment.value?.kind === 'receiving' &&
    !appointment.value.lot &&
    ['scheduled', 'confirmed'].includes(appointment.value.status),
)

async function remove() {
  if (!appointment.value) return
  try {
    await deleteAppointment(appointment.value.id)
    notifications.notify(t('inventory.appointments.deleted'))
    emit('saved')
    open.value = false
  } catch (error) {
    notifications.notify(deleteErrorMessage(error, t('common.deleteError')), 'error')
  }
}
</script>

<template>
  <FormDialog
    ref="formRef"
    v-model="open"
    :title="appointment ? appointment.code : $t('inventory.appointments.new')"
    :subtitle="appointment ? $t(`inventory.appointments.kinds.${appointment.kind}`) : null"
    icon="mdi-calendar-clock"
    max-width="960"
    :persistent="saving"
    @submit="submit"
  >
    <template v-if="appointment" #heading-end>
      <AppointmentStatusChip :status="appointment.status" />
    </template>
    <template v-if="showExpected" #header>
      <v-tabs v-model="tab" density="compact">
        <v-tab value="details">{{ $t('inventory.appointments.details') }}</v-tab>
        <v-tab value="expected" data-testid="tab-expected">
          {{ $t('inventory.expected.title') }}
          <v-chip v-if="rows.length" size="x-small" class="ml-2">{{ rows.length }}</v-chip>
        </v-tab>
      </v-tabs>
    </template>

    <v-progress-linear v-if="loading" indeterminate class="mb-4" />

    <v-alert
      v-if="appointment?.conflicts.length"
      type="warning"
      variant="tonal"
      density="compact"
      class="mb-4"
      data-testid="conflicts"
    >
      {{ $t('inventory.appointments.conflicts', { codes: appointment.conflicts.join(', ') }) }}
    </v-alert>

    <v-window v-model="tab">
      <v-window-item value="details">
        <v-row dense>
          <v-col cols="12" md="4">
            <v-btn-toggle
              v-model="kind"
              mandatory
              color="primary"
              variant="outlined"
              divided
              class="w-100"
              :disabled="readonly || isEdit"
              data-testid="kind"
            >
              <v-btn value="receiving" prepend-icon="mdi-tray-arrow-down" class="flex-grow-1">
                {{ $t('inventory.appointments.kinds.receiving') }}
              </v-btn>
              <v-btn value="shipping" prepend-icon="mdi-tray-arrow-up" class="flex-grow-1">
                {{ $t('inventory.appointments.kinds.shipping') }}
              </v-btn>
            </v-btn-toggle>
          </v-col>
          <v-col cols="12" md="8">
            <v-select
              v-model="warehouseId"
              :items="warehouseOptions"
              :label="$t('inventory.fields.warehouse')"
              :rules="required"
              :error-messages="fieldErrors.warehouse"
              :disabled="readonly"
              data-testid="warehouse"
            />
          </v-col>
          <v-col cols="12">
            <CustomerSelect
              :key="`customer-${openCount}-${appointment?.id ?? 0}`"
              v-model="customer"
              :label="$t('inventory.appointments.customer')"
              :initial-option="
                appointment?.customer
                  ? { id: appointment.customer, name: appointment.customer_name ?? '' }
                  : null
              "
              :rules="kind === 'receiving' ? required : []"
              :error-messages="fieldErrors.customer"
              :disabled="readonly"
              data-testid="customer"
            />
          </v-col>
          <v-col cols="12" md="4">
            <v-text-field
              v-model="date"
              type="date"
              :label="$t('inventory.appointments.date')"
              :rules="required"
              :error-messages="fieldErrors.starts_at"
              :disabled="readonly"
              data-testid="date"
            />
          </v-col>
          <v-col cols="6" md="4">
            <v-text-field
              v-model="startTime"
              type="time"
              :label="$t('inventory.appointments.from')"
              :rules="required"
              :disabled="readonly"
              data-testid="start-time"
            />
          </v-col>
          <v-col cols="6" md="4">
            <v-text-field
              v-model="endTime"
              type="time"
              :label="$t('inventory.appointments.to')"
              :rules="[
                ...required,
                () => endTime > startTime || $t('inventory.appointments.endAfterStart'),
              ]"
              :error-messages="fieldErrors.ends_at"
              :disabled="readonly"
              data-testid="end-time"
            />
          </v-col>
        </v-row>

        <div class="text-subtitle-2 text-medium-emphasis mb-2 mt-2">
          {{ $t('inventory.appointments.transport') }}
        </div>
        <v-row dense>
          <v-col cols="12" md="6">
            <ServiceProviderPicker
              :key="`carrier-${openCount}-${appointment?.id ?? 0}`"
              v-model="carrier"
              service="transport"
              :initial-option="appointment?.carrier_detail ?? null"
              :label="$t('inventory.appointments.carrier')"
              :error-messages="fieldErrors.carrier"
              :disabled="readonly"
              clearable
            />
          </v-col>
          <v-col cols="12" md="6">
            <v-text-field
              v-model="carrierName"
              :label="$t('inventory.appointments.carrierName')"
              :hint="$t('inventory.appointments.carrierNameHint')"
              persistent-hint
              maxlength="150"
              :disabled="readonly"
            />
          </v-col>
          <v-col cols="12" md="4">
            <v-text-field
              v-model="plate"
              :label="$t('inventory.appointments.plate')"
              maxlength="20"
              :disabled="readonly"
            />
          </v-col>
          <v-col cols="12" md="5">
            <v-text-field
              v-model="driver"
              :label="$t('inventory.appointments.driver')"
              maxlength="150"
              :disabled="readonly"
            />
          </v-col>
          <v-col cols="12" md="3">
            <v-text-field
              v-model="volumes"
              :label="$t('inventory.appointments.volumes')"
              :rules="[(v: string) => !v || /^\d+$/.test(v) || $t('inventory.labels.countRule')]"
              inputmode="numeric"
              :disabled="readonly"
            />
          </v-col>
          <v-col cols="12">
            <v-textarea
              v-model="notes"
              :label="$t('customers.fields.notes')"
              rows="2"
              auto-grow
              :disabled="readonly"
            />
          </v-col>
        </v-row>
        <p v-if="appointment?.lot" class="text-body-2">
          {{ $t('inventory.appointments.lot') }}:
          <router-link :to="{ name: 'inventory-lot', params: { id: appointment.lot.id } }">
            {{ appointment.lot.code }}
          </router-link>
        </p>
      </v-window-item>

      <v-window-item v-if="showExpected" value="expected">
        <p class="text-body-2 text-medium-emphasis mb-3">{{ $t('inventory.expected.hint') }}</p>
        <ExpectedItemsEditor ref="editor" v-model="rows" :readonly="readonly" />
        <v-alert
          v-if="fieldErrors.expected_items"
          type="error"
          variant="tonal"
          density="compact"
          class="mt-2"
        >
          {{ fieldErrors.expected_items.join(' ') }}
        </v-alert>
      </v-window-item>
    </v-window>

    <v-alert v-if="generalError" type="error" variant="tonal" density="compact" class="mt-2">
      {{ generalError }}
    </v-alert>

    <template #actions>
      <v-btn
        v-if="appointment && canSchedule && !appointment.lot && appointment.status !== 'done'"
        variant="text"
        color="error"
        prepend-icon="mdi-delete-outline"
        @click="remove"
      >
        {{ $t('common.delete') }}
      </v-btn>
      <v-btn
        v-for="action in statusActions"
        :key="action.status"
        variant="text"
        :prepend-icon="action.icon"
        :data-testid="`status-${action.status}`"
        @click="changeStatus(action.status)"
      >
        {{ $t(`inventory.appointments.actions.${action.status}`) }}
      </v-btn>
      <v-btn
        v-if="canOpenLot"
        variant="tonal"
        color="primary"
        prepend-icon="mdi-truck-check-outline"
        data-testid="open-lot"
        @click="appointment && emit('openLot', appointment)"
      >
        {{ $t('inventory.lots.start') }}
      </v-btn>
      <v-spacer />
      <v-btn variant="text" :disabled="saving" @click="open = false">
        {{ $t(readonly ? 'common.close' : 'common.cancel') }}
      </v-btn>
      <v-btn
        v-if="!readonly"
        type="submit"
        color="primary"
        variant="flat"
        :loading="saving"
        data-testid="save"
      >
        {{ $t('common.save') }}
      </v-btn>
    </template>
  </FormDialog>
</template>
