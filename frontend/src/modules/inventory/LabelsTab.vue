<script setup lang="ts">
/**
 * Labels: reserve a range of Horizon IDs and print them in advance (read at triage, each ID
 * binds to one asset), print a range again, and reprint the label of anything by reading or
 * typing its code — always the same code (RN-16).
 */
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { ApiError } from '@/api'
import ServerCrudTable from '@/components/ServerCrudTable.vue'
import { useDateFormat } from '@/composables/useDateFormat'
import { useNotificationsStore } from '@/stores/notifications'
import { parseCode } from '@/utils/inventoryCodes'
import {
  listLabelRanges,
  lookupCode,
  reprintAsset,
  reprintContainer,
  reserveLabelRange,
  type LabelRange,
} from './api'
import { printLabels, rangeLabels, type Label } from './labels'

const { t } = useI18n()
const { d } = useDateFormat()
const notifications = useNotificationsStore()

const table = ref<{ reload: () => Promise<void> } | null>(null)

// --- Reserve a range -------------------------------------------------------------------------

const count = ref('50')
const reserving = ref(false)
const countRule = (v: string) =>
  (/^\d+$/.test(v) && Number(v) >= 1 && Number(v) <= 1000) || t('inventory.labels.countRule')

async function reserve() {
  if (countRule(count.value) !== true) return
  reserving.value = true
  try {
    const range = await reserveLabelRange(Number(count.value))
    notifications.notify(
      t('inventory.labels.reserved', { first: range.first_code, last: range.last_code }),
    )
    printRange(range)
    table.value?.reload()
  } catch (error) {
    notifications.notify(error instanceof ApiError ? error.message : t('common.saveError'), 'error')
  } finally {
    reserving.value = false
  }
}

function printRange(range: LabelRange) {
  printLabels(
    rangeLabels(range.first_number, range.last_number),
    `${range.first_code}–${range.last_code}`,
  )
}

// --- Reprint by code -------------------------------------------------------------------------

const reading = ref('')
const reprintError = ref('')

async function reprintByCode() {
  reprintError.value = ''
  const parsed = parseCode(reading.value)
  if (parsed.kind !== 'location' && !parsed.valid) {
    reprintError.value =
      parsed.kind === 'unknown'
        ? t('inventory.movement.unknownCode', { code: parsed.code })
        : t('inventory.movement.wrongDigit')
    return
  }
  try {
    const found = await lookupCode(parsed.code)
    let label: Label
    if (found.kind === 'asset') {
      await reprintAsset(found.item.id)
      const m = found.item.asset_model_detail
      label = {
        code: found.item.horizon_id,
        title: `${m.manufacturer_name} ${m.name}`,
        subtitle: found.item.serial,
      }
    } else if (found.kind === 'container') {
      await reprintContainer(found.item.id)
      label = {
        code: found.item.code,
        title: t(`inventory.containerKinds.${found.item.kind}`),
        subtitle: found.item.description,
      }
    } else {
      label = {
        code: found.item.code,
        title: '',
        subtitle: found.item.description || t(`inventory.areas.${found.item.area_type}`),
      }
    }
    printLabels([label], label.code)
    reading.value = ''
  } catch (error) {
    reprintError.value = error instanceof ApiError ? error.message : t('common.saveError')
  }
}

const headers = computed(() => [
  { title: t('inventory.labels.range'), key: 'first_code', sortable: false },
  { title: t('inventory.labels.size'), key: 'size', sortable: false, width: 120 },
  { title: t('inventory.labels.reservedBy'), key: 'reserved_by_name', sortable: false },
  { title: t('inventory.labels.reservedAt'), key: 'reserved_at', sortable: false, width: 200 },
])
</script>

<template>
  <v-row>
    <v-col cols="12" md="6">
      <v-card class="pa-4 h-100">
        <div class="text-subtitle-1 font-weight-medium mb-1">
          {{ $t('inventory.labels.reserveTitle') }}
        </div>
        <p class="text-body-2 text-medium-emphasis mb-4">
          {{ $t('inventory.labels.reserveText') }}
        </p>
        <div class="d-flex align-start ga-3">
          <v-text-field
            v-model="count"
            :label="$t('inventory.labels.count')"
            :rules="[countRule]"
            inputmode="numeric"
            density="compact"
            style="max-width: 180px"
            data-testid="count"
            @keydown.enter.prevent="reserve"
          />
          <v-btn
            color="primary"
            prepend-icon="mdi-printer-outline"
            :loading="reserving"
            data-testid="reserve"
            @click="reserve"
          >
            {{ $t('inventory.labels.reserveAndPrint') }}
          </v-btn>
        </div>
      </v-card>
    </v-col>
    <v-col cols="12" md="6">
      <v-card class="pa-4 h-100">
        <div class="text-subtitle-1 font-weight-medium mb-1">
          {{ $t('inventory.labels.reprintTitle') }}
        </div>
        <p class="text-body-2 text-medium-emphasis mb-4">
          {{ $t('inventory.labels.reprintText') }}
        </p>
        <v-text-field
          v-model="reading"
          :label="$t('inventory.labels.code')"
          :error-messages="reprintError"
          prepend-inner-icon="mdi-barcode-scan"
          autocomplete="off"
          density="compact"
          data-testid="reprint-code"
          @keydown.enter.prevent="reprintByCode"
          @update:model-value="reprintError = ''"
        />
      </v-card>
    </v-col>
  </v-row>

  <div class="text-subtitle-1 font-weight-medium mt-6 mb-2">
    {{ $t('inventory.labels.ranges') }}
  </div>
  <ServerCrudTable
    ref="table"
    :fetch-page="listLabelRanges"
    :delete-item="async () => undefined"
    :headers="headers"
    :sort-by="[{ key: 'reserved_at', order: 'desc' }]"
    :search-placeholder="''"
    :empty-text="$t('inventory.labels.empty')"
    :no-results-text="$t('inventory.labels.empty')"
    delete-title=""
    :delete-message="() => ''"
    deleted-text=""
    hide-create
    :can-delete="() => false"
    edit-icon="mdi-printer-outline"
    :edit-title="$t('inventory.labels.printAgain')"
    @edit="printRange"
  >
    <template #[`item.first_code`]="{ item }">
      <span class="font-weight-medium">{{ item.first_code }} – {{ item.last_code }}</span>
    </template>
    <template #[`item.reserved_at`]="{ item }">{{
      d(new Date(item.reserved_at), 'dateTime')
    }}</template>
  </ServerCrudTable>
</template>
