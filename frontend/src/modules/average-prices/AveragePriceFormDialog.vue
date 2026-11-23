<script setup lang="ts">
/**
 * Create an average price, or a new version of an existing one (`source`): rows are never
 * edited. The asset class decides the terms (its sub-vertical's allowed terms) and the
 * specification fields (its sub-vertical's template). Values typed are resolved by the API
 * preview (value ↔ % and warnings), never computed here.
 */
import FormDialog from '@/components/FormDialog.vue'
import WebSearchButton from '@/components/WebSearchButton.vue'
import KeywordsField from '@/components/KeywordsField.vue'
import MoneyField from '@/components/MoneyField.vue'
import { computed, nextTick, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { ApiError } from '@/api'
import { useValidationRules } from '@/composables/useValidationRules'
import AssetClassPicker from '@/modules/catalogs/asset-classes/AssetClassPicker.vue'
import { getAssetClass, type AssetClass } from '@/modules/catalogs/asset-classes/api'
import ManufacturerPicker from '@/modules/catalogs/manufacturers/ManufacturerPicker.vue'
import { parseMoney, toInputMoney, toInputNumber } from '@/utils/money'
import SpecValuesInput from './SpecValuesInput.vue'
import { parseTermInput } from './termInput'
import TermPointsInput, { type TermEntry } from './TermPointsInput.vue'
import {
  createAveragePrice,
  previewAveragePrice,
  type AveragePrice,
  type AveragePriceDetail,
  type PreviewResult,
  type PricePointInput,
} from './api'

const CURRENCY = 'BRL' // only currency for now; the API already stores it per row

const props = defineProps<{ source: AveragePrice | null }>()
const open = defineModel<boolean>({ required: true })
const emit = defineEmits<{ saved: [row: AveragePriceDetail, newVersion: boolean] }>()

const { t, locale } = useI18n()
const rules = useValidationRules()

const assetClassId = ref<number | null>(null)
const assetClass = ref<AssetClass | null>(null)
const manufacturerId = ref<number | null>(null)
const model = ref('')
const description = ref('')
/** Two tabs: the asset (what it is) and its eFMV (original value and value per term) */
type Tab = 'asset' | 'efmv'
const tab = ref<Tab>('asset')
const keywords = ref<string[]>([])
const specs = ref<Record<string, string>>({})
const originalText = ref('')
const entries = ref<Record<number, TermEntry>>({})

const fieldErrors = ref<Record<string, string[]>>({})
const specErrors = ref<Record<string, string[]>>({})
const termErrors = ref<Record<number, string[]>>({})
const generalError = ref('')
const saving = ref(false)
const loadingSource = ref(false)
const resolved = ref<PreviewResult | null>(null)
const formRef = ref<{ validate: () => Promise<{ valid: boolean }> } | null>(null)
const openCount = ref(0) // remounts the pickers on every open

const isNewVersion = computed(() => props.source !== null)
const subVertical = computed(() => assetClass.value?.sub_vertical_detail ?? null)
const terms = computed(() => subVertical.value?.allowed_terms ?? [])
const template = computed(() => assetClass.value?.spec_template ?? [])
const required = [(v: unknown) => (v !== null && v !== undefined) || t('validation.required')]
const originalRules = [
  (v: string) => !!v?.trim() || t('validation.required'),
  (v: string) => {
    const value = parseMoney(v, locale.value)
    return (value !== null && Number(value) > 0) || t('averagePrices.invalidValue')
  },
]

/** Terms of the (new) sub-vertical, keeping what was typed for terms that remain. */
function rebuildEntries(previous: Record<number, TermEntry>) {
  entries.value = Object.fromEntries(
    terms.value.map((term) => [term, previous[term] ?? { text: '' }]),
  )
}

function onAssetClassSelected(selected: AssetClass | null) {
  assetClass.value = selected
  rebuildEntries(entries.value)
  fieldErrors.value.asset_class = []
}

watch(open, async (isOpen) => {
  if (!isOpen) return
  fieldErrors.value = {}
  specErrors.value = {}
  termErrors.value = {}
  generalError.value = ''
  resolved.value = null
  openCount.value += 1
  tab.value = 'asset'

  const s = props.source
  assetClassId.value = s?.asset_class.id ?? null
  assetClass.value = null
  manufacturerId.value = s?.manufacturer.id ?? null
  model.value = s?.model ?? ''
  description.value = s?.description ?? ''
  // A new version starts with the previous one's keywords
  keywords.value = [...(s?.keywords ?? [])]
  originalText.value = s ? toInputNumber(s.original_value, locale.value, 2, 2) : ''
  specs.value = Object.fromEntries(
    (s?.specs ?? []).map((spec) => [
      spec.key,
      spec.kind === 'number' && spec.value
        ? toInputNumber(spec.value, locale.value, 0, 6)
        : spec.value,
    ]),
  )
  const previous: Record<number, TermEntry> = Object.fromEntries(
    (s?.points ?? []).map((p) => [
      p.term_months,
      // As the eFMV cells: the value (a % typed back then is shown as its value)
      { text: toInputMoney(p.value, locale.value) },
    ]),
  )
  entries.value = {}

  if (s) {
    // The new version follows the asset class's current terms and template
    loadingSource.value = true
    try {
      assetClass.value = await getAssetClass(s.asset_class.id)
    } catch {
      generalError.value = t('common.loadError')
    } finally {
      loadingSource.value = false
    }
  }
  rebuildEntries(previous)
})

// --- Preview: the API resolves values and warnings while the user types --------------------

function typedPoints(): PricePointInput[] | null {
  const points: PricePointInput[] = []
  for (const term of terms.value) {
    const entry = entries.value[term]
    if (!entry) return null
    const parsed = parseTermInput(entry.text, locale.value)
    if (parsed === null) return null
    points.push({ term_months: term, ...parsed })
  }
  return points.length ? points : null
}

let previewTimer: ReturnType<typeof setTimeout> | undefined
let previewRequest = 0

watch(
  [originalText, entries, terms],
  () => {
    clearTimeout(previewTimer)
    previewTimer = setTimeout(async () => {
      const original = parseMoney(originalText.value, locale.value)
      const points = typedPoints()
      const request = ++previewRequest
      if (!original || Number(original) <= 0 || !points) {
        resolved.value = null
        return
      }
      try {
        const result = await previewAveragePrice({ original_value: original, points })
        if (request === previewRequest) resolved.value = result
      } catch {
        if (request === previewRequest) resolved.value = null
      }
    }, 400)
  },
  { deep: true },
)

// --- Save ------------------------------------------------------------------------------------

function canonicalSpecs(): Record<string, string> {
  return Object.fromEntries(
    template.value.map((field) => {
      const text = specs.value[field.key] ?? ''
      const value =
        field.kind === 'number' && text.trim() ? (parseMoney(text, locale.value, 6) ?? text) : text
      return [field.key, value]
    }),
  )
}

/** Open the first tab with a field in error (both tabs stay mounted, so both validate). */
async function openTabWithErrors() {
  await nextTick()
  const field = document.querySelector('[data-form-tab] .v-input--error')
  const name = field?.closest<HTMLElement>('[data-form-tab]')?.dataset.formTab
  if (name === 'asset' || name === 'efmv') tab.value = name
}

function applyErrors(body: Record<string, unknown>, sentTerms: number[]) {
  const { specs: specErr, points: pointErr, ...rest } = body
  fieldErrors.value = Object.fromEntries(
    Object.entries(rest).filter(([, v]) => Array.isArray(v)),
  ) as Record<string, string[]>
  specErrors.value = (specErr as Record<string, string[]>) ?? {}
  if (Array.isArray(pointErr)) {
    generalError.value = pointErr.join(' ')
  } else if (pointErr && typeof pointErr === 'object') {
    // Per position, in the order the terms were sent
    termErrors.value = Object.fromEntries(
      Object.entries(pointErr as Record<string, Record<string, string[]>>).map(([i, err]) => [
        sentTerms[Number(i)],
        Object.values(err).flat(),
      ]),
    )
  }
  if (!Object.keys(body).length) generalError.value = t('common.saveError')
}

async function submit() {
  const result = await formRef.value?.validate()
  const points = typedPoints()
  const original = parseMoney(originalText.value, locale.value)
  if (
    !result?.valid ||
    assetClassId.value === null ||
    manufacturerId.value === null ||
    !points ||
    !original
  ) {
    await openTabWithErrors()
    return
  }

  saving.value = true
  fieldErrors.value = {}
  specErrors.value = {}
  termErrors.value = {}
  generalError.value = ''
  try {
    const saved = await createAveragePrice({
      asset_class: assetClassId.value,
      manufacturer: manufacturerId.value,
      model: model.value.trim(),
      description: description.value.trim(),
      keywords: keywords.value,
      specs: canonicalSpecs(),
      currency: CURRENCY,
      original_value: original,
      points,
      supersedes: props.source?.id ?? null,
    })
    emit('saved', saved, isNewVersion.value)
    open.value = false
  } catch (error) {
    const body = error instanceof ApiError && error.status === 400 ? error.data : null
    if (body && typeof body === 'object') {
      applyErrors(
        body as Record<string, unknown>,
        points.map((p) => p.term_months),
      )
      await openTabWithErrors()
    } else {
      generalError.value = t('common.saveError')
    }
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <FormDialog
    ref="formRef"
    v-model="open"
    :title="isNewVersion ? $t('averagePrices.newVersion') : $t('averagePrices.new')"
    :subtitle="source ? `${source.manufacturer.name} ${source.model}` : null"
    icon="mdi-chart-timeline-variant"
    max-width="980"
    :persistent="saving"
    @submit="submit"
  >
    <!-- The asset's value: what matters most, in the header on the right (both tabs) -->
    <template #heading-end>
      <MoneyField
        v-model="originalText"
        :currency="CURRENCY"
        :label="$t('averagePrices.fields.originalValue')"
        :rules="originalRules"
        :error-messages="fieldErrors.original_value"
        density="comfortable"
        hide-details="auto"
        class="original-value"
        data-testid="original-value"
      />
    </template>
    <template #header>
      <v-tabs v-model="tab" color="primary" density="compact" class="mt-2">
        <v-tab value="asset" prepend-icon="mdi-cube-outline" data-testid="tab-asset">
          {{ $t('averagePrices.formTabs.asset') }}
        </v-tab>
        <v-tab value="efmv" prepend-icon="mdi-chart-line" data-testid="tab-efmv">
          {{ $t('averagePrices.formTabs.efmv') }}
        </v-tab>
      </v-tabs>
    </template>

    <v-progress-linear v-if="loadingSource" indeterminate class="mb-4" />

    <!-- Every tab stays mounted (eager) so the form validates both -->
    <!-- Room for the first fields' floating labels (the window clips its content) -->
    <v-window v-model="tab" class="pt-2">
      <!-- The asset: what it is -->
      <v-window-item
        value="asset"
        eager
        :transition="false"
        :reverse-transition="false"
        data-form-tab="asset"
      >
        <v-row dense>
          <v-col cols="12" md="7">
            <AssetClassPicker
              :key="`asset-${openCount}-${loadingSource}`"
              v-model="assetClassId"
              :initial-option="assetClass"
              :label="$t('averagePrices.fields.assetClass')"
              :rules="required"
              :error-messages="fieldErrors.asset_class"
              data-testid="asset-class"
              @selected="onAssetClassSelected"
            />
          </v-col>
          <v-col cols="12" md="5">
            <ManufacturerPicker
              :key="`manufacturer-${openCount}`"
              v-model="manufacturerId"
              :initial-option="source?.manufacturer ?? null"
              :label="$t('averagePrices.fields.manufacturer')"
              :rules="required"
              :error-messages="fieldErrors.manufacturer"
              data-testid="manufacturer"
            />
          </v-col>
          <v-col cols="12">
            <v-text-field
              v-model="model"
              :label="$t('averagePrices.fields.model')"
              :rules="[rules.required, rules.maxLength(150)]"
              :error-messages="fieldErrors.model"
              maxlength="150"
              data-testid="model"
            >
              <template #append-inner><WebSearchButton :term="model" /></template>
            </v-text-field>
          </v-col>
          <v-col cols="12">
            <v-textarea
              v-model="description"
              :label="$t('averagePrices.fields.description')"
              :hint="$t('averagePrices.descriptionHint')"
              persistent-hint
              :error-messages="fieldErrors.description"
              rows="3"
              auto-grow
              data-testid="description"
            />
          </v-col>
          <v-col cols="12">
            <KeywordsField
              v-model="keywords"
              :error-messages="fieldErrors.keywords"
              data-testid="keywords"
              @update:model-value="fieldErrors.keywords = []"
            />
          </v-col>
        </v-row>

        <!-- Specifications (template of the sub-vertical) -->
        <template v-if="subVertical">
          <div class="text-subtitle-1 mt-2">{{ $t('averagePrices.sections.specs') }}</div>
          <p class="text-body-2 text-medium-emphasis mb-2">{{ subVertical.label }}</p>
          <SpecValuesInput
            v-model="specs"
            :template="template"
            :asset-class-id="assetClass?.id ?? null"
            :errors="specErrors"
          />
        </template>
      </v-window-item>

      <!-- Its eFMV: the original value and the value at each term -->
      <v-window-item
        value="efmv"
        eager
        :transition="false"
        :reverse-transition="false"
        data-form-tab="efmv"
      >
        <p v-if="!subVertical" class="text-body-2 text-medium-emphasis">
          {{ $t('averagePrices.chooseAssetClassFirst') }}
        </p>
        <template v-else>
          <p class="text-body-2 text-medium-emphasis mb-2">
            {{ $t('averagePrices.termsHint') }}
          </p>
          <TermPointsInput
            v-model="entries"
            :terms="terms"
            :currency="CURRENCY"
            :resolved="resolved"
            :errors="termErrors"
          />
          <v-alert
            v-if="resolved?.increasing_terms.length"
            type="warning"
            variant="tonal"
            density="compact"
            class="mt-3"
            data-testid="increasing-warning"
          >
            {{
              $t('averagePrices.increasingWarning', {
                terms: resolved.increasing_terms.join(', '),
              })
            }}
          </v-alert>
        </template>
      </v-window-item>
    </v-window>

    <v-alert v-if="generalError" type="error" variant="tonal" density="compact" class="mt-3">
      {{ generalError }}
    </v-alert>

    <template #actions>
      <v-btn variant="text" :disabled="saving" @click="open = false">
        {{ $t('common.cancel') }}
      </v-btn>
      <v-btn
        type="submit"
        color="primary"
        variant="flat"
        :loading="saving"
        :disabled="loadingSource"
        data-testid="save"
      >
        {{ isNewVersion ? $t('averagePrices.saveNewVersion') : $t('common.save') }}
      </v-btn>
    </template>
  </FormDialog>
</template>

<style scoped>
.original-value {
  width: 260px;
}
.original-value :deep(input) {
  font-size: 1.125rem;
  font-weight: 600;
}
</style>
