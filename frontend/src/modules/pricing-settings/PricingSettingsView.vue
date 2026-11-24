<script setup lang="ts">
/**
 * Pricing control panel (administrators): the limits that place a value typed in an eFMV
 * analysis against Average Prices, and how long an average price stays current.
 */
import { useDateFormat } from '@/composables/useDateFormat'
import { computed, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useNumberFormat } from '@/composables/useNumberFormat'
import { ApiError } from '@/api'
import { useValidationRules } from '@/composables/useValidationRules'
import { useNotificationsStore } from '@/stores/notifications'
import { isDecimalInRange, normalizeDecimal } from '@/utils/decimal'
import { getPricingSettings, updatePricingSettings, type PricingSettings } from './api'

const { t } = useI18n()
const { n } = useNumberFormat()
// Dates in the formats the user chose (Settings)
const { d } = useDateFormat()
const rules = useValidationRules()
const notifications = useNotificationsStore()

const loading = ref(true)
const loadFailed = ref(false)
const saving = ref(false)
const saved = ref<PricingSettings | null>(null)
const errors = ref<Record<string, string[]>>({})
const form = ref<{ validate: () => Promise<{ valid: boolean }> } | null>(null)

const compatible = ref('')
const below = ref('')
const above = ref('')
const months = ref('')
const acceptExpired = ref(true)

// Shown as typed in the UI language ("7,5" in pt-br)
const toInput = (value: string) => n(Number(value), 'decimal')

function fill(data: PricingSettings) {
  saved.value = data
  compatible.value = toInput(data.compatible_percent)
  below.value = toInput(data.below_percent)
  above.value = toInput(data.above_percent)
  months.value = String(data.validity_months)
  acceptExpired.value = data.accept_expired
}

async function load() {
  loading.value = true
  loadFailed.value = false
  try {
    fill(await getPricingSettings())
  } catch {
    loadFailed.value = true
  } finally {
    loading.value = false
  }
}
onMounted(load)

const percentRules = [rules.required, rules.decimalRange(0, 100, 2)]
const beyondCompatible = (v: string) =>
  !isDecimalInRange(v ?? '', 0, 100, 2) ||
  !isDecimalInRange(compatible.value ?? '', 0, 100, 2) ||
  Number(normalizeDecimal(v)) > Number(normalizeDecimal(compatible.value)) ||
  t('pricingSettings.beyondCompatible')
const monthRules = [
  rules.required,
  (v: string) =>
    (/^\d+$/.test(v?.trim() ?? '') && Number(v) >= 1 && Number(v) <= 120) ||
    t('pricingSettings.monthsRange'),
]

/** The five ranges as they will be applied, for the preview scale */
const scale = computed(() => {
  const valid = [compatible.value, below.value, above.value].every((v) =>
    isDecimalInRange(v ?? '', 0, 100, 2),
  )
  if (!valid) return null
  const pct = (v: string) => `${n(Number(normalizeDecimal(v)), 'percentValue')}%`
  return [
    { key: 'below', color: 'error', range: `≤ −${pct(below.value)}` },
    { key: 'slightly_below', color: 'warning', range: `−${pct(below.value)} … −${pct(compatible.value)}` },
    { key: 'compatible', color: 'success', range: `± ${pct(compatible.value)}` },
    { key: 'slightly_above', color: 'warning', range: `+${pct(compatible.value)} … +${pct(above.value)}` },
    { key: 'above', color: 'error', range: `≥ +${pct(above.value)}` },
  ] // prettier-ignore
})

async function save() {
  errors.value = {}
  const { valid } = (await form.value?.validate()) ?? { valid: false }
  if (!valid) return
  saving.value = true
  try {
    fill(
      await updatePricingSettings({
        compatible_percent: normalizeDecimal(compatible.value),
        below_percent: normalizeDecimal(below.value),
        above_percent: normalizeDecimal(above.value),
        validity_months: Number(months.value),
        accept_expired: acceptExpired.value,
      }),
    )
    notifications.notify(t('pricingSettings.saved'))
  } catch (error) {
    if (error instanceof ApiError && error.status === 400) errors.value = error.fieldErrors()
    notifications.notify(t('common.saveError'), 'error')
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <v-container style="max-width: 900px">
    <h1 class="text-h5 mb-1">{{ $t('pricingSettings.title') }}</h1>
    <p class="text-medium-emphasis mb-6">{{ $t('pricingSettings.subtitle') }}</p>

    <v-progress-linear v-if="loading" indeterminate />
    <v-alert v-else-if="loadFailed" type="error" variant="tonal">
      {{ $t('common.loadError') }}
      <template #append>
        <v-btn variant="text" size="small" @click="load">{{ $t('common.retry') }}</v-btn>
      </template>
    </v-alert>

    <v-form v-else ref="form" @submit.prevent="save">
      <v-card class="mb-4">
        <v-card-item prepend-icon="mdi-scale-balance">
          <v-card-title>{{ $t('pricingSettings.positioning.title') }}</v-card-title>
          <v-card-subtitle class="text-wrap">
            {{ $t('pricingSettings.positioning.subtitle') }}
          </v-card-subtitle>
        </v-card-item>
        <v-card-text>
          <v-row dense>
            <v-col cols="12" sm="4">
              <v-text-field
                v-model="below"
                :label="$t('pricingSettings.positioning.below')"
                :hint="$t('pricingSettings.positioning.belowHint')"
                persistent-hint
                suffix="%"
                inputmode="decimal"
                :rules="[...percentRules, beyondCompatible]"
                :error-messages="errors.below_percent"
                data-testid="below"
              />
            </v-col>
            <v-col cols="12" sm="4">
              <v-text-field
                v-model="compatible"
                :label="$t('pricingSettings.positioning.compatible')"
                :hint="$t('pricingSettings.positioning.compatibleHint')"
                persistent-hint
                prefix="±"
                suffix="%"
                inputmode="decimal"
                :rules="percentRules"
                :error-messages="errors.compatible_percent"
                data-testid="compatible"
              />
            </v-col>
            <v-col cols="12" sm="4">
              <v-text-field
                v-model="above"
                :label="$t('pricingSettings.positioning.above')"
                :hint="$t('pricingSettings.positioning.aboveHint')"
                persistent-hint
                suffix="%"
                inputmode="decimal"
                :rules="[...percentRules, beyondCompatible]"
                :error-messages="errors.above_percent"
                data-testid="above"
              />
            </v-col>
          </v-row>
          <div v-if="scale" class="scale mt-6" data-testid="scale">
            <v-sheet
              v-for="band in scale"
              :key="band.key"
              :color="band.color"
              class="band pa-2 text-center"
              rounded
            >
              <div class="text-caption font-weight-medium">
                {{ $t(`efmv.position.${band.key}`) }}
              </div>
              <div class="text-caption text-no-wrap">{{ band.range }}</div>
            </v-sheet>
          </div>
        </v-card-text>
      </v-card>

      <v-card class="mb-4">
        <v-card-item prepend-icon="mdi-calendar-clock">
          <v-card-title>{{ $t('pricingSettings.validity.title') }}</v-card-title>
          <v-card-subtitle class="text-wrap">
            {{ $t('pricingSettings.validity.subtitle') }}
          </v-card-subtitle>
        </v-card-item>
        <v-card-text>
          <v-row dense align="center">
            <v-col cols="12" sm="4">
              <v-text-field
                v-model="months"
                :label="$t('pricingSettings.validity.months')"
                :suffix="$t('efmv.scenario.months')"
                inputmode="numeric"
                :rules="monthRules"
                :error-messages="errors.validity_months"
                data-testid="validity-months"
              />
            </v-col>
            <v-col cols="12" sm="8">
              <v-switch
                v-model="acceptExpired"
                color="primary"
                :label="$t('pricingSettings.validity.acceptExpired')"
                :hint="
                  $t(
                    acceptExpired
                      ? 'pricingSettings.validity.acceptExpiredOn'
                      : 'pricingSettings.validity.acceptExpiredOff',
                  )
                "
                persistent-hint
                inset
                data-testid="accept-expired"
              />
            </v-col>
          </v-row>
        </v-card-text>
      </v-card>

      <div class="d-flex align-center ga-3">
        <span v-if="saved?.updated_by_name" class="text-caption text-medium-emphasis mr-auto">
          {{
            $t('pricingSettings.lastChange', {
              date: d(new Date(saved.updated_at), 'short'),
              name: saved.updated_by_name,
            })
          }}
        </span>
        <v-spacer v-else />
        <v-btn
          color="primary"
          type="submit"
          prepend-icon="mdi-cloud-upload-outline"
          :loading="saving"
          data-testid="save"
        >
          {{ $t('common.save') }}
        </v-btn>
      </div>
    </v-form>
  </v-container>
</template>

<style scoped>
.scale {
  display: grid;
  grid-template-columns: repeat(5, 1fr);
  gap: 4px;
}
@media (max-width: 599.98px) {
  .scale {
    grid-template-columns: 1fr;
  }
}
</style>
