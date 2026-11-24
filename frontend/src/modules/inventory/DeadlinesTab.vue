<script setup lang="ts">
/**
 * Deadlines (block release, report dispute, dispute analysis: days, calendar or business days,
 * reminders), the holidays business days skip, the days an asset may stay in each status
 * before an alert, and "Check Deadlines Now" (the daily routine, which cron runs every day).
 */
import { computed, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { ApiError } from '@/api'
import { useDateFormat } from '@/composables/useDateFormat'
import { useNotificationsStore } from '@/stores/notifications'
import {
  createHoliday,
  deleteHoliday,
  listAgingLimits,
  listDeadlineSettings,
  listHolidays,
  runDeadlineCheck,
  updateAgingLimit,
  updateDeadlineSetting,
  type AgingLimit,
  type DeadlineSetting,
  type Holiday,
} from './api'
import { useInventoryRoles } from './roles'

const { t } = useI18n()
const { d } = useDateFormat()
const notifications = useNotificationsStore()
const { isSupervisor } = useInventoryRoles()

const settings = ref<DeadlineSetting[]>([])
const limits = ref<AgingLimit[]>([])
const holidays = ref<Holiday[]>([])
const year = ref(new Date().getFullYear())
const newDate = ref('')
const newName = ref('')
const running = ref(false)

async function load() {
  ;[settings.value, limits.value] = await Promise.all([listDeadlineSettings(), listAgingLimits()])
  await loadHolidays()
}
async function loadHolidays() {
  holidays.value = (await listHolidays(year.value)).results
}
onMounted(load)

function fail(error: unknown) {
  notifications.notify(error instanceof ApiError ? error.message : t('common.saveError'), 'error')
}

async function saveSetting(setting: DeadlineSetting, data: Partial<DeadlineSetting>) {
  try {
    Object.assign(setting, await updateDeadlineSetting(setting.id, data))
    notifications.notify(t('inventory.deadlines.saved'))
  } catch (error) {
    fail(error)
  }
}

function reminders(setting: DeadlineSetting, text: string) {
  const days = text
    .split(/[,;\s]+/)
    .map((part) => Number(part))
    .filter((n) => Number.isInteger(n) && n > 0)
  saveSetting(setting, { reminder_days: days })
}

async function saveLimit(limit: AgingLimit, text: string) {
  const days = text.trim() ? Number(text) : null
  if (days !== null && (!Number.isInteger(days) || days < 1)) return
  try {
    Object.assign(limit, await updateAgingLimit(limit.id, days))
  } catch (error) {
    fail(error)
  }
}

async function addHoliday() {
  if (!newDate.value || !newName.value.trim()) return
  try {
    await createHoliday({ date: newDate.value, name: newName.value })
    newDate.value = ''
    newName.value = ''
    await loadHolidays()
  } catch (error) {
    fail(error)
  }
}

async function removeHoliday(holiday: Holiday) {
  try {
    await deleteHoliday(holiday.id)
    await loadHolidays()
  } catch (error) {
    fail(error)
  }
}

async function runNow() {
  running.value = true
  try {
    const counts = await runDeadlineCheck()
    notifications.notify(t('inventory.deadlines.checked', counts))
  } catch (error) {
    fail(error)
  } finally {
    running.value = false
  }
}

const years = computed(() => [year.value - 1, year.value, year.value + 1])
const day = (value: string) => d(new Date(`${value}T12:00`), 'short')
</script>

<template>
  <div>
    <div class="d-flex flex-wrap align-center ga-3 mb-4">
      <span class="text-body-2 text-medium-emphasis">{{
        $t('inventory.deadlines.routineHint')
      }}</span>
      <v-spacer />
      <v-btn
        v-if="isSupervisor"
        variant="tonal"
        prepend-icon="mdi-timer-sand-complete"
        :loading="running"
        data-testid="run-check"
        @click="runNow"
      >
        {{ $t('inventory.deadlines.runNow') }}
      </v-btn>
    </div>

    <v-row>
      <v-col v-for="setting in settings" :key="setting.id" cols="12" md="4">
        <v-card class="pa-4 h-100" :data-testid="`deadline-${setting.kind}`">
          <div class="text-subtitle-1 font-weight-medium mb-3">
            {{ $t(`inventory.deadlines.kinds.${setting.kind}`) }}
          </div>
          <div class="d-flex ga-3">
            <v-text-field
              :model-value="setting.days"
              :label="$t('inventory.deadlines.days')"
              inputmode="numeric"
              density="compact"
              :readonly="!isSupervisor"
              style="max-width: 110px"
              @change="
                (e: Event) =>
                  saveSetting(setting, { days: Number((e.target as HTMLInputElement).value) })
              "
            />
            <v-select
              :model-value="setting.business_days"
              :items="[
                { value: false, title: $t('inventory.deadlines.calendarDays') },
                { value: true, title: $t('inventory.deadlines.businessDays') },
              ]"
              density="compact"
              :readonly="!isSupervisor"
              @update:model-value="saveSetting(setting, { business_days: $event })"
            />
          </div>
          <v-text-field
            :model-value="setting.reminder_days.join(', ')"
            :label="$t('inventory.deadlines.reminders')"
            :hint="$t('inventory.deadlines.remindersHint')"
            persistent-hint
            density="compact"
            :readonly="!isSupervisor"
            @change="(e: Event) => reminders(setting, (e.target as HTMLInputElement).value)"
          />
        </v-card>
      </v-col>
    </v-row>

    <v-row class="mt-2">
      <v-col cols="12" md="6">
        <v-card class="pa-4 h-100">
          <div class="d-flex align-center mb-2">
            <div class="text-subtitle-1 font-weight-medium flex-grow-1">
              {{ $t('inventory.deadlines.holidays') }}
            </div>
            <v-select
              v-model="year"
              :items="years"
              density="compact"
              hide-details
              style="max-width: 120px"
              @update:model-value="loadHolidays"
            />
          </div>
          <p class="text-body-2 text-medium-emphasis mb-3">
            {{ $t('inventory.deadlines.holidaysHint') }}
          </p>
          <div v-if="isSupervisor" class="d-flex ga-2 mb-2">
            <v-text-field
              v-model="newDate"
              type="date"
              density="compact"
              hide-details
              style="max-width: 170px"
              data-testid="holiday-date"
            />
            <v-text-field
              v-model="newName"
              :placeholder="$t('inventory.deadlines.holidayName')"
              density="compact"
              hide-details
              data-testid="holiday-name"
              @keydown.enter.prevent="addHoliday"
            />
            <v-btn color="primary" data-testid="holiday-add" @click="addHoliday">{{
              $t('common.new')
            }}</v-btn>
          </div>
          <v-list density="compact" data-testid="holidays">
            <v-list-item v-for="h in holidays" :key="h.id" class="px-0">
              <v-list-item-title>{{ day(h.date) }} · {{ h.name }}</v-list-item-title>
              <template v-if="isSupervisor" #append>
                <v-btn
                  icon="mdi-delete-outline"
                  size="small"
                  variant="text"
                  color="error"
                  @click="removeHoliday(h)"
                />
              </template>
            </v-list-item>
            <v-list-item v-if="!holidays.length" class="px-0 text-medium-emphasis">
              {{ $t('inventory.deadlines.noHolidays') }}
            </v-list-item>
          </v-list>
        </v-card>
      </v-col>
      <v-col cols="12" md="6">
        <v-card class="pa-4 h-100">
          <div class="text-subtitle-1 font-weight-medium mb-1">
            {{ $t('inventory.deadlines.aging') }}
          </div>
          <p class="text-body-2 text-medium-emphasis mb-3">
            {{ $t('inventory.deadlines.agingHint') }}
          </p>
          <v-table density="compact">
            <tbody>
              <tr v-for="limit in limits" :key="limit.id">
                <td>{{ $t(`inventory.statuses.${limit.status}`) }}</td>
                <td style="width: 140px">
                  <v-text-field
                    :model-value="limit.days ?? ''"
                    :placeholder="$t('inventory.deadlines.noLimit')"
                    :suffix="$t('inventory.deadlines.daysShort')"
                    inputmode="numeric"
                    density="compact"
                    hide-details
                    :readonly="!isSupervisor"
                    @change="(e: Event) => saveLimit(limit, (e.target as HTMLInputElement).value)"
                  />
                </td>
              </tr>
            </tbody>
          </v-table>
        </v-card>
      </v-col>
    </v-row>
  </div>
</template>
