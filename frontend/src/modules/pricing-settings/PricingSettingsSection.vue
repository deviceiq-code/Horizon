<script setup lang="ts">
/**
 * Pricing's app settings (Settings › App Settings, administrators): the limits that place a
 * value typed in an eFMV analysis against Average Prices, and how long an average price stays
 * current; and the disclaimer closing an analysis's printed report, in every language. Laid out
 * as the rest of Settings (cards of SettingRows); as there, every change is
 * saved on its own: a field when it is left (or Enter), the switch at once.
 */
import { computed, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { ApiError } from '@/api'
import SettingRow from '@/components/SettingRow.vue'
import { useDateFormat } from '@/composables/useDateFormat'
import { useNumberFormat } from '@/composables/useNumberFormat'
import { useValidationRules } from '@/composables/useValidationRules'
import { useNotificationsStore } from '@/stores/notifications'
import { LANGUAGES } from '@/i18n'
import { isDecimalInRange, normalizeDecimal } from '@/utils/decimal'
import { DISCLAIMER_VARIABLES, MAX_DISCLAIMER } from '@/modules/efmv-analyses/report'
import {
  getPricingSettings,
  updatePricingSettings,
  type PricingSettings,
  type PricingSettingsInput,
} from './api'

const { t } = useI18n()
const { n } = useNumberFormat()
// Dates in the formats the user chose
const { d } = useDateFormat()
const notifications = useNotificationsStore()
const rules = useValidationRules()

const loading = ref(true)
const loadFailed = ref(false)
const saving = ref(false)
const saved = ref<PricingSettings | null>(null)
const errors = ref<Record<string, string[]>>({})

const compatible = ref('')
const below = ref('')
const above = ref('')
const months = ref('')
/** The disclaimer as typed, per language */
const disclaimers = ref<Record<string, string>>({})

// Shown as typed in the UI language ("7,5" in pt-br)
const toInput = (value: string) => n(Number(value), 'decimal')

function fill(data: PricingSettings) {
  saved.value = data
  compatible.value = toInput(data.compatible_percent)
  below.value = toInput(data.below_percent)
  above.value = toInput(data.above_percent)
  months.value = String(data.validity_months)
  disclaimers.value = Object.fromEntries(
    LANGUAGES.map(({ code }) => [code, data.report_disclaimer[code] ?? '']),
  )
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

// --- Rules (the API checks them again) -------------------------------------------------------

const isPercent = (v: string) => isDecimalInRange(v ?? '', 0, 100, 2)
const number = (v: string) => Number(normalizeDecimal(v))
const percentRules: Rule[] = [rules.required, rules.decimalRange(0, 100, 2)]
/** Below / above the historical value start beyond the compatible range */
const beyondCompatible = (v: string) =>
  !isPercent(v) || !isPercent(compatible.value) || number(v) > number(compatible.value) ||
  t('pricingSettings.beyondCompatible') // prettier-ignore
const withinLimits = (v: string) =>
  !isPercent(v) ||
  [below.value, above.value].every((limit) => !isPercent(limit) || number(v) < number(limit)) ||
  t('pricingSettings.withinLimits')
const monthRule = (v: string) =>
  (/^\d+$/.test(v?.trim() ?? '') && Number(v) >= 1 && Number(v) <= 120) ||
  t('pricingSettings.monthsRange')

type Rule = (v: string) => true | string
type PercentField = 'compatible_percent' | 'below_percent' | 'above_percent'
const PERCENT_FIELDS: Record<PercentField, { text: typeof compatible; rules: Rule[] }> = {
  compatible_percent: { text: compatible, rules: [...percentRules, withinLimits] },
  below_percent: { text: below, rules: [...percentRules, beyondCompatible] },
  above_percent: { text: above, rules: [...percentRules, beyondCompatible] },
}
const passes = (value: string, rules: Rule[]) => rules.every((rule) => rule(value) === true)

/** The five ranges as they are applied (the values typed), for the scale */
const scale = computed(() => {
  if (![compatible.value, below.value, above.value].every(isPercent)) return null
  const pct = (v: string) => `${n(number(v), 'percentValue')}%`
  return [
    { key: 'below', color: 'error', range: `≤ −${pct(below.value)}` },
    { key: 'slightly_below', color: 'warning', range: `−${pct(below.value)} … −${pct(compatible.value)}` },
    { key: 'compatible', color: 'success', range: `± ${pct(compatible.value)}` },
    { key: 'slightly_above', color: 'warning', range: `+${pct(compatible.value)} … +${pct(above.value)}` },
    { key: 'above', color: 'error', range: `≥ +${pct(above.value)}` },
  ] // prettier-ignore
})

// --- Saving: one change at a time -------------------------------------------------------------

async function save(changes: Partial<PricingSettingsInput>) {
  saving.value = true
  errors.value = {}
  try {
    fill(await updatePricingSettings(changes))
    notifications.notify(t('settings.saved'))
  } catch (error) {
    if (error instanceof ApiError && error.status === 400) errors.value = error.fieldErrors()
    notifications.notify(t('settings.saveError'), 'error')
  } finally {
    saving.value = false
  }
}

/** A percentage, when left: saved if valid and changed */
function savePercent(field: PercentField) {
  const { text, rules } = PERCENT_FIELDS[field]
  if (!saved.value || !passes(text.value, rules)) return
  const value = normalizeDecimal(text.value)
  if (number(value) !== Number(saved.value[field])) save({ [field]: value })
}

/** A language's disclaimer, when left: saved if changed */
function saveDisclaimer(code: string) {
  const text = (disclaimers.value[code] ?? '').trim()
  if (!saved.value || text.length > MAX_DISCLAIMER) return
  if (text !== (saved.value.report_disclaimer[code] ?? '')) {
    save({ report_disclaimer: { [code]: text } })
  }
}

function restoreDisclaimer(code: string) {
  disclaimers.value[code] = saved.value?.report_disclaimer_defaults[code] ?? ''
  saveDisclaimer(code)
}

/** "{code}": how a variable is written in the text */
const asVariable = (name: string) => `{${name}}`

const disclaimerRules = [
  (v: string) =>
    (v ?? '').length <= MAX_DISCLAIMER || t('validation.maxLength', { max: MAX_DISCLAIMER }),
]

function saveMonths() {
  if (!saved.value || monthRule(months.value) !== true) return
  const value = Number(months.value.trim())
  if (value !== saved.value.validity_months) save({ validity_months: value })
}
</script>

<template>
  <v-progress-linear v-if="loading" indeterminate class="mb-6" />
  <v-alert v-else-if="loadFailed" type="error" variant="tonal" class="mb-6">
    {{ $t('common.loadError') }}
    <template #append>
      <v-btn variant="text" size="small" @click="load">{{ $t('common.retry') }}</v-btn>
    </template>
  </v-alert>

  <template v-else-if="saved">
    <!-- How a unit value typed in an analysis compares with its average price -->
    <div class="group-title">{{ $t('pricingSettings.positioning.title') }}</div>
    <v-card class="mb-6" data-testid="pricing-positioning">
      <SettingRow
        :title="$t('pricingSettings.positioning.below')"
        :description="$t('pricingSettings.positioning.belowHint')"
      >
        <v-text-field
          v-model="below"
          suffix="%"
          inputmode="decimal"
          :rules="PERCENT_FIELDS.below_percent.rules"
          :error-messages="errors.below_percent"
          :disabled="saving"
          density="compact"
          hide-details="auto"
          class="control-narrow"
          :aria-label="$t('pricingSettings.positioning.below')"
          data-testid="below"
          @update:model-value="errors.below_percent = []"
          @blur="savePercent('below_percent')"
          @keydown.enter="savePercent('below_percent')"
        />
      </SettingRow>
      <SettingRow
        :title="$t('pricingSettings.positioning.compatible')"
        :description="$t('pricingSettings.positioning.compatibleHint')"
      >
        <v-text-field
          v-model="compatible"
          prefix="±"
          suffix="%"
          inputmode="decimal"
          :rules="PERCENT_FIELDS.compatible_percent.rules"
          :error-messages="errors.compatible_percent"
          :disabled="saving"
          density="compact"
          hide-details="auto"
          class="control-narrow"
          :aria-label="$t('pricingSettings.positioning.compatible')"
          data-testid="compatible"
          @update:model-value="errors.compatible_percent = []"
          @blur="savePercent('compatible_percent')"
          @keydown.enter="savePercent('compatible_percent')"
        />
      </SettingRow>
      <SettingRow
        :title="$t('pricingSettings.positioning.above')"
        :description="$t('pricingSettings.positioning.aboveHint')"
      >
        <v-text-field
          v-model="above"
          suffix="%"
          inputmode="decimal"
          :rules="PERCENT_FIELDS.above_percent.rules"
          :error-messages="errors.above_percent"
          :disabled="saving"
          density="compact"
          hide-details="auto"
          class="control-narrow"
          :aria-label="$t('pricingSettings.positioning.above')"
          data-testid="above"
          @update:model-value="errors.above_percent = []"
          @blur="savePercent('above_percent')"
          @keydown.enter="savePercent('above_percent')"
        />
      </SettingRow>
      <!-- The five ranges these limits make -->
      <SettingRow
        v-if="scale"
        :title="$t('pricingSettings.positioning.scale')"
        :description="$t('pricingSettings.positioning.subtitle')"
      >
        <template #below>
          <div class="scale" data-testid="scale">
            <v-sheet
              v-for="band in scale"
              :key="band.key"
              :color="band.color"
              class="pa-2 text-center"
              rounded
            >
              <div class="text-caption font-weight-medium">
                {{ $t(`efmv.position.${band.key}`) }}
              </div>
              <div class="text-caption text-no-wrap">{{ band.range }}</div>
            </v-sheet>
          </div>
        </template>
      </SettingRow>
    </v-card>

    <!-- How long an average price stays current -->
    <div class="group-title">{{ $t('pricingSettings.validity.title') }}</div>
    <v-card class="mb-2" data-testid="pricing-validity">
      <SettingRow
        :title="$t('pricingSettings.validity.months')"
        :description="$t('pricingSettings.validity.subtitle')"
      >
        <v-text-field
          v-model="months"
          :suffix="$t('efmv.scenario.months')"
          inputmode="numeric"
          :rules="[monthRule]"
          :error-messages="errors.validity_months"
          :disabled="saving"
          density="compact"
          hide-details="auto"
          class="control-narrow"
          :aria-label="$t('pricingSettings.validity.months')"
          data-testid="validity-months"
          @update:model-value="errors.validity_months = []"
          @blur="saveMonths"
          @keydown.enter="saveMonths"
        />
      </SettingRow>
      <SettingRow :title="$t('pricingSettings.validity.acceptExpired')">
        <template #description>
          <span data-testid="accept-expired-hint">
            {{
              $t(
                saved.accept_expired
                  ? 'pricingSettings.validity.acceptExpiredOn'
                  : 'pricingSettings.validity.acceptExpiredOff',
              )
            }}
          </span>
        </template>
        <v-switch
          :model-value="saved.accept_expired"
          color="primary"
          inset
          hide-details
          density="compact"
          :disabled="saving"
          :aria-label="$t('pricingSettings.validity.acceptExpired')"
          data-testid="accept-expired"
          @update:model-value="save({ accept_expired: !!$event })"
        />
      </SettingRow>
    </v-card>
    <!-- The disclaimer closing an analysis's printed report, in every language -->
    <div class="group-title">{{ $t('pricingSettings.report.title') }}</div>
    <v-card class="mb-2" data-testid="pricing-report">
      <SettingRow
        v-for="language in LANGUAGES"
        :key="language.code"
        :title="$t('pricingSettings.report.disclaimer', { language: language.name })"
        :description="$t('pricingSettings.report.disclaimerHint')"
      >
        <template #below>
          <v-textarea
            v-model="disclaimers[language.code]"
            :rules="disclaimerRules"
            :error-messages="errors.report_disclaimer"
            :disabled="saving"
            rows="4"
            auto-grow
            density="compact"
            hide-details="auto"
            :aria-label="$t('pricingSettings.report.disclaimer', { language: language.name })"
            :data-testid="`disclaimer-${language.code}`"
            @update:model-value="errors.report_disclaimer = []"
            @blur="saveDisclaimer(language.code)"
          />
          <div class="d-flex flex-wrap align-center ga-2 mt-2">
            <span class="text-caption text-medium-emphasis">{{
              $t('pricingSettings.report.variables')
            }}</span>
            <v-chip
              v-for="variable in DISCLAIMER_VARIABLES"
              :key="variable"
              size="x-small"
              label
              :title="$t(`pricingSettings.report.variable.${variable}`)"
              >{{ asVariable(variable) }}</v-chip
            >
            <v-spacer />
            <v-btn
              variant="text"
              size="small"
              prepend-icon="mdi-restore"
              :disabled="
                saving ||
                disclaimers[language.code] === saved.report_disclaimer_defaults[language.code]
              "
              :data-testid="`disclaimer-restore-${language.code}`"
              @click="restoreDisclaimer(language.code)"
              >{{ $t('pricingSettings.report.restore') }}</v-btn
            >
          </div>
        </template>
      </SettingRow>
    </v-card>
    <div
      v-if="saved.updated_by_name"
      class="text-caption text-medium-emphasis mb-6 ml-1"
      data-testid="pricing-last-change"
    >
      {{
        $t('pricingSettings.lastChange', {
          date: d(new Date(saved.updated_at), 'short'),
          name: saved.updated_by_name,
        })
      }}
    </div>
  </template>
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
