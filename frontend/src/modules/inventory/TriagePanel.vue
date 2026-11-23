<script setup lang="ts">
/**
 * Triage of a lot with the barcode gun — blind count: nothing expected is shown.
 * Units: (container, optional and kept) → label (pre-printed; empty = a new ID, printed at
 * once) → model (kept for the next ones) → serial (Enter saves). Without a serial: the reason
 * and a photo. Accessories (models controlled by quantity): quantity into a container or the
 * dock, damaged ones to a scrap area.
 */
import { nextTick, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { ApiError } from '@/api'
import AssetModelPicker from '@/modules/catalogs/asset-models/AssetModelPicker.vue'
import type { AssetModel } from '@/modules/catalogs/asset-models/api'
import { parseCode } from '@/utils/inventoryCodes'
import { NO_SERIAL_REASONS, triageAccessories, triageUnit, type Asset, type Lot } from './api'
import { beep } from './beep'
import { printLabels } from './labels'

const props = defineProps<{ lot: Lot }>()
const emit = defineEmits<{ changed: [] }>()

const { t } = useI18n()

type Feedback = { kind: 'success' | 'error'; text: string } | null
const mode = ref<'unit' | 'accessory'>('unit')
const feedback = ref<Feedback>(null)
const busy = ref(false)
const count = ref(0)

function ok(text: string) {
  feedback.value = { kind: 'success', text }
  beep(true)
}

function fail(error: unknown) {
  const text =
    error instanceof ApiError && error.message
      ? error.message
      : typeof error === 'string'
        ? error
        : t('common.saveError')
  feedback.value = { kind: 'error', text }
  beep(false)
}

// --- Units -------------------------------------------------------------------------------------

const container = ref('')
const label = ref('')
const model = ref<number | null>(null)
const modelInfo = ref<AssetModel | null>(null)
const serial = ref('')
const noSerial = ref(false)
const reason = ref<string | null>(null)
const photo = ref<File | null>(null)
const labelField = ref<{ focus: () => void } | null>(null)
const serialField = ref<{ focus: () => void } | null>(null)

const reasons = NO_SERIAL_REASONS.map((value) => ({
  value,
  title: t(`inventory.noSerialReasons.${value}`),
}))

function focusLabel() {
  nextTick(() => labelField.value?.focus())
}

function onLabelEnter() {
  const text = label.value.trim()
  if (text) {
    const parsed = parseCode(text)
    if (parsed.kind !== 'asset' || !parsed.valid) return fail(t('inventory.movement.wrongDigit'))
    label.value = parsed.code
  }
  nextTick(() => serialField.value?.focus())
}

async function saveUnit() {
  if (busy.value) return
  if (!model.value) return fail(t('inventory.triage.chooseModel'))
  if (!serial.value.trim() && (!noSerial.value || !reason.value || !photo.value)) {
    noSerial.value = true
    return fail(t('inventory.triage.noSerialNeeds'))
  }
  busy.value = true
  try {
    const asset: Asset = await triageUnit(props.lot.id, {
      asset_model: model.value,
      horizon_id: label.value.trim(),
      serial: serial.value,
      no_serial_reason: serial.value.trim() ? '' : (reason.value ?? ''),
      container_code: container.value.trim(),
      photo: serial.value.trim() ? null : photo.value,
    })
    count.value += 1
    ok(t('inventory.triage.unitSaved', { code: asset.horizon_id }))
    if (!label.value.trim()) {
      // A new ID: its label is printed now
      const m = asset.asset_model_detail
      printLabels(
        [
          {
            code: asset.horizon_id,
            title: `${m.manufacturer_name} ${m.name}`,
            subtitle: asset.serial,
          },
        ],
        asset.horizon_id,
      )
    }
    label.value = ''
    serial.value = ''
    noSerial.value = false
    reason.value = null
    photo.value = null
    emit('changed')
    focusLabel()
  } catch (error) {
    fail(error)
  } finally {
    busy.value = false
  }
}

// --- Accessories -------------------------------------------------------------------------------

const accessoryModel = ref<number | null>(null)
const quantity = ref('')
const accessoryContainer = ref('')
const damaged = ref('')
const scrap = ref('')
const accessoryKey = ref(0)

const whole = (v: string) => (/^\d+$/.test(v.trim()) ? Number(v) : v.trim() ? -1 : 0)

async function saveAccessories() {
  if (busy.value) return
  if (!accessoryModel.value) return fail(t('inventory.triage.chooseModel'))
  const good = whole(quantity.value)
  const bad = whole(damaged.value)
  if (good < 0 || bad < 0 || good + bad < 1) return fail(t('inventory.triage.quantityRule'))
  busy.value = true
  try {
    await triageAccessories(props.lot.id, {
      asset_model: accessoryModel.value,
      quantity: good,
      container_code: accessoryContainer.value.trim(),
      damaged_quantity: bad,
      scrap_code: scrap.value.trim(),
    })
    ok(t('inventory.triage.accessoriesSaved', { count: good + bad }))
    quantity.value = ''
    damaged.value = ''
    accessoryModel.value = null
    accessoryKey.value += 1
    emit('changed')
  } catch (error) {
    fail(error)
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <div>
    <div class="d-flex flex-wrap align-center ga-3 mb-4">
      <v-btn-toggle v-model="mode" mandatory density="compact" variant="outlined" divided>
        <v-btn value="unit" prepend-icon="mdi-barcode-scan" data-testid="mode-unit">
          {{ $t('inventory.triage.units') }}
        </v-btn>
        <v-btn value="accessory" prepend-icon="mdi-counter" data-testid="mode-accessory">
          {{ $t('inventory.triage.accessories') }}
        </v-btn>
      </v-btn-toggle>
      <v-chip variant="tonal" label>{{ $t('inventory.triage.count', count) }}</v-chip>
      <span class="text-caption text-medium-emphasis">{{ $t('inventory.triage.blind') }}</span>
    </div>

    <v-alert
      v-if="feedback"
      :type="feedback.kind"
      variant="tonal"
      class="mb-4 feedback"
      data-testid="triage-feedback"
    >
      {{ feedback.text }}
    </v-alert>

    <!-- Units -->
    <v-row v-if="mode === 'unit'" dense>
      <v-col cols="12" md="4">
        <v-text-field
          v-model="container"
          :label="$t('inventory.triage.container')"
          :hint="$t('inventory.triage.containerHint')"
          persistent-hint
          prepend-inner-icon="mdi-package-variant"
          autocomplete="off"
          clearable
          data-testid="triage-container"
          @keydown.enter.prevent="focusLabel"
        />
      </v-col>
      <v-col cols="12" md="8">
        <AssetModelPicker
          v-model="model"
          tracking="unit"
          :label="$t('inventory.fields.assetModel')"
          :hint="$t('inventory.triage.modelHint')"
          persistent-hint
          data-testid="triage-model"
          @selected="modelInfo = $event"
        />
      </v-col>
      <v-col cols="12" md="5">
        <v-text-field
          ref="labelField"
          v-model="label"
          :label="$t('inventory.triage.label')"
          :hint="$t('inventory.triage.labelHint')"
          persistent-hint
          prepend-inner-icon="mdi-barcode-scan"
          autocomplete="off"
          autofocus
          class="scan-field"
          data-testid="triage-label"
          @keydown.enter.prevent="onLabelEnter"
        />
      </v-col>
      <v-col cols="12" md="7">
        <v-text-field
          ref="serialField"
          v-model="serial"
          :label="$t('inventory.fields.serial')"
          :hint="
            modelInfo?.serial_regex
              ? $t('inventory.triage.pattern', { pattern: modelInfo.serial_regex })
              : ''
          "
          persistent-hint
          prepend-inner-icon="mdi-barcode-scan"
          autocomplete="off"
          class="scan-field"
          data-testid="triage-serial"
          @keydown.enter.prevent="saveUnit"
        />
      </v-col>
      <v-col cols="12">
        <v-checkbox
          v-model="noSerial"
          :label="$t('inventory.triage.noSerial')"
          hide-details
          density="compact"
          data-testid="triage-no-serial"
        />
      </v-col>
      <template v-if="noSerial && !serial.trim()">
        <v-col cols="12" md="6">
          <v-select
            v-model="reason"
            :items="reasons"
            :label="$t('inventory.fields.noSerialReason')"
            data-testid="triage-reason"
          />
        </v-col>
        <v-col cols="12" md="6">
          <v-file-input
            v-model="photo"
            accept="image/*"
            :label="$t('inventory.triage.photo')"
            prepend-icon=""
            prepend-inner-icon="mdi-camera-outline"
            data-testid="triage-photo"
          />
        </v-col>
      </template>
      <v-col cols="12" class="d-flex justify-end">
        <v-btn
          color="primary"
          size="large"
          prepend-icon="mdi-check"
          :loading="busy"
          data-testid="triage-save"
          @click="saveUnit"
        >
          {{ $t('inventory.triage.saveUnit') }}
        </v-btn>
      </v-col>
    </v-row>

    <!-- Accessories -->
    <v-row v-else dense>
      <v-col cols="12" md="6">
        <AssetModelPicker
          :key="accessoryKey"
          v-model="accessoryModel"
          tracking="quantity"
          :label="$t('inventory.fields.assetModel')"
          data-testid="accessory-model"
        />
      </v-col>
      <v-col cols="6" md="3">
        <v-text-field
          v-model="quantity"
          :label="$t('inventory.triage.goodQuantity')"
          inputmode="numeric"
          data-testid="accessory-quantity"
        />
      </v-col>
      <v-col cols="6" md="3">
        <v-text-field
          v-model="accessoryContainer"
          :label="$t('inventory.triage.container')"
          :hint="$t('inventory.triage.accessoryContainerHint')"
          persistent-hint
          prepend-inner-icon="mdi-package-variant"
          autocomplete="off"
          data-testid="accessory-container"
        />
      </v-col>
      <v-col cols="6" md="3">
        <v-text-field
          v-model="damaged"
          :label="$t('inventory.triage.damagedQuantity')"
          inputmode="numeric"
          data-testid="accessory-damaged"
        />
      </v-col>
      <v-col cols="6" md="5">
        <v-text-field
          v-model="scrap"
          :label="$t('inventory.triage.scrapDestination')"
          :disabled="!damaged.trim()"
          prepend-inner-icon="mdi-recycle"
          autocomplete="off"
          data-testid="accessory-scrap"
        />
      </v-col>
      <v-col cols="12" md="4" class="d-flex justify-end align-center">
        <v-btn
          color="primary"
          size="large"
          prepend-icon="mdi-check"
          :loading="busy"
          data-testid="accessory-save"
          @click="saveAccessories"
        >
          {{ $t('inventory.triage.saveAccessories') }}
        </v-btn>
      </v-col>
    </v-row>
  </div>
</template>

<style scoped>
.scan-field :deep(input) {
  font-size: 1.25rem;
  letter-spacing: 0.04em;
}
.feedback {
  font-size: 1.05rem;
}
</style>
