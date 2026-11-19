<script setup lang="ts">
/**
 * Create an average price, or a new version of an existing one (`source`): rows are never
 * edited. The asset class decides the terms (its sub-vertical's allowed terms) and the
 * specification fields (its sub-vertical's template). Values typed are resolved by the API
 * preview (value ↔ % and warnings), never computed here.
 */
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { ApiError } from '@/api'
import { useValidationRules } from '@/composables/useValidationRules'
import AssetClassPicker from '@/modules/catalogs/asset-classes/AssetClassPicker.vue'
import { getAssetClass, type AssetClass } from '@/modules/catalogs/asset-classes/api'
import ManufacturerPicker from '@/modules/catalogs/manufacturers/ManufacturerPicker.vue'
import { parseMoney, toInputNumber } from '@/utils/money'
import SpecValuesInput from './SpecValuesInput.vue'
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
    terms.value.map((term) => [term, previous[term] ?? { mode: 'percent', text: '' }]),
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

  const s = props.source
  assetClassId.value = s?.asset_class.id ?? null
  assetClass.value = null
  manufacturerId.value = s?.manufacturer.id ?? null
  model.value = s?.model ?? ''
  description.value = s?.description ?? ''
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
      {
        mode: p.mode,
        text:
          p.mode === 'value'
            ? toInputNumber(p.amount, locale.value, 2, 2)
            : toInputNumber(p.amount, locale.value, 0, 4),
      },
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
    const amount = parseMoney(entry.text, locale.value, entry.mode === 'percent' ? 4 : 2)
    if (amount === null) return null
    points.push({ term_months: term, mode: entry.mode, amount })
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
  if (!result?.valid || assetClassId.value === null || manufacturerId.value === null) return
  const points = typedPoints()
  const original = parseMoney(originalText.value, locale.value)
  if (!points || !original) return

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
    } else {
      generalError.value = t('common.saveError')
    }
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <v-dialog v-model="open" max-width="980" scrollable :persistent="saving">
    <v-card
      :title="isNewVersion ? $t('averagePrices.newVersion') : $t('averagePrices.new')"
      :subtitle="isNewVersion ? $t('averagePrices.newVersionHint') : undefined"
    >
      <v-form
        ref="formRef"
        class="d-flex flex-column"
        style="min-height: 0"
        @submit.prevent="submit"
      >
        <v-card-text>
          <v-progress-linear v-if="loadingSource" indeterminate class="mb-4" />

          <!-- Asset -->
          <div class="text-subtitle-1 mb-2">{{ $t('averagePrices.sections.asset') }}</div>
          <v-row dense>
            <v-col cols="12" md="7">
              <AssetClassPicker
                :key="`asset-${openCount}`"
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
              />
            </v-col>
            <v-col cols="12">
              <v-textarea
                v-model="description"
                :label="$t('averagePrices.fields.description')"
                :hint="$t('averagePrices.descriptionHint')"
                persistent-hint
                :rules="[rules.required]"
                :error-messages="fieldErrors.description"
                rows="3"
                auto-grow
                data-testid="description"
              />
            </v-col>
          </v-row>

          <!-- Specifications (template of the sub-vertical) -->
          <template v-if="subVertical">
            <div class="text-subtitle-1 mt-4">{{ $t('averagePrices.sections.specs') }}</div>
            <p class="text-body-2 text-medium-emphasis mb-2">{{ subVertical.label }}</p>
            <SpecValuesInput v-model="specs" :template="template" :errors="specErrors" />
          </template>

          <!-- Values -->
          <div class="text-subtitle-1 mt-4 mb-2">{{ $t('averagePrices.sections.values') }}</div>
          <v-text-field
            v-model="originalText"
            :label="$t('averagePrices.fields.originalValue')"
            :prefix="CURRENCY"
            inputmode="decimal"
            :rules="originalRules"
            :error-messages="fieldErrors.original_value"
            style="max-width: 320px"
            data-testid="original-value"
          />
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

          <v-alert v-if="generalError" type="error" variant="tonal" density="compact" class="mt-3">
            {{ generalError }}
          </v-alert>
        </v-card-text>

        <v-card-actions>
          <v-spacer />
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
        </v-card-actions>
      </v-form>
    </v-card>
  </v-dialog>
</template>
