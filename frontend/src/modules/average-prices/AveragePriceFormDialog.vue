<script setup lang="ts">
/**
 * Create an average price, or a new version of an existing one (`source`): rows are never
 * edited. With `copy`, `source` only fills the form: a new, separate price (not a version)
 * starting with its asset, specifications, values, keywords and photo — the documents stay with
 * the original. The asset class decides the terms (its sub-vertical's allowed terms) and the
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
  applyMediaChanges,
  hasMediaChanges,
  noMediaChanges,
  type MediaChanges,
  type SaveOutcome,
} from './media'
import PriceMediaTab from './PriceMediaTab.vue'
import { useNotificationsStore } from '@/stores/notifications'
import {
  createAveragePrice,
  pricePhotoUrl,
  previewAveragePrice,
  type AveragePrice,
  type AveragePriceDetail,
  type PreviewResult,
  type PricePointInput,
} from './api'

const CURRENCY = 'BRL' // only currency for now; the API already stores it per row

const props = withDefaults(
  defineProps<{
    source: AveragePrice | null
    /** A copy of `source` (a new price of its own), not a new version of it */
    copy?: boolean
    /** A new price's model to start with (e.g. what was searched for and not found) */
    initialModel?: string
    /** Only asset classes of this vertical / sub-vertical (e.g. an eFMV analysis's scope) */
    scopeVertical?: number | null
    scopeSubVertical?: number | null
  }>(),
  { copy: false, initialModel: '', scopeVertical: null, scopeSubVertical: null },
)
const open = defineModel<boolean>({ required: true })
// `saved`: a new price, a new version, or only its photo and documents (no version; row null)
const emit = defineEmits<{ saved: [row: AveragePriceDetail | null, outcome: SaveOutcome] }>()
const notifications = useNotificationsStore()

const { t, locale } = useI18n()
const rules = useValidationRules()

const assetClassId = ref<number | null>(null)
const assetClass = ref<AssetClass | null>(null)
const manufacturerId = ref<number | null>(null)
const manufacturerName = ref('')
/** A model is searched with its manufacturer ("Dell P2423H"); nothing without the model */
const modelSearchTerm = computed(() =>
  model.value.trim() ? `${manufacturerName.value} ${model.value}`.trim() : '',
)
const model = ref('')
const description = ref('')
/** Three tabs: the asset (what it is), its eFMV (value per term) and its photo and documents
 * (the row's, pending until saved) */
type Tab = 'asset' | 'efmv' | 'media'
const media = ref<MediaChanges>(noMediaChanges())
/** The photo search's words: manufacturer, model and asset class */
const photoSearchTerm = computed(() =>
  [manufacturerName.value, model.value.trim(), assetClass.value?.name ?? '']
    .filter(Boolean)
    .join(' '),
)
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

const isNewVersion = computed(() => props.source !== null && !props.copy)
const isCopy = computed(() => props.source !== null && props.copy)
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
  media.value = noMediaChanges()

  const s = props.source
  assetClassId.value = s?.asset_class.id ?? null
  assetClass.value = null
  manufacturerId.value = s?.manufacturer.id ?? null
  manufacturerName.value = s?.manufacturer.name ?? ''
  model.value = s?.model ?? props.initialModel.trim()
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
  if (s && props.copy && s.photo_id !== null) await copyPhoto(s.id, s.photo_id)
})

/** A copy starts with the original's photo: fetched here and sent as a file when saved */
async function copyPhoto(rowId: number, photoId: number) {
  try {
    const response = await fetch(pricePhotoUrl(rowId, photoId), { credentials: 'same-origin' })
    if (!response.ok) return
    const blob = await response.blob()
    const extension = blob.type.split('/')[1] || 'jpg'
    const file = new File([blob], `photo.${extension}`, { type: blob.type })
    media.value = {
      ...media.value,
      photo: { kind: 'file', file, preview: URL.createObjectURL(file) },
    }
  } catch {
    // Without the photo: one can still be chosen in the form
  }
}

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

/** Whether the price itself (not its photo and documents) is as in the version it came from */
function sameAsSource(points: PricePointInput[], original: string): boolean {
  const s = props.source
  if (!s) return false
  const sameList = (a: string[], b: string[]) =>
    a.length === b.length && a.every((x, i) => x === b[i])
  const specsNow = canonicalSpecs()
  const specsBefore = Object.fromEntries(s.specs.map((spec) => [spec.key, spec]))
  // A field empty now and absent before (or the other way round) is the same
  const keys = new Set([...Object.keys(specsNow), ...Object.keys(specsBefore)])
  const sameSpecs = [...keys].every((key) => {
    const now = (specsNow[key] ?? '').trim()
    const before = specsBefore[key]
    const was = before?.value ?? ''
    return before?.kind === 'number' && now && was ? Number(now) === Number(was) : now === was
  })
  const pointsBefore = Object.fromEntries(s.points.map((p) => [p.term_months, p]))
  const samePoints =
    points.length === s.points.length &&
    points.every((p) => {
      const before = pointsBefore[p.term_months]
      if (!before) return false
      return p.mode === 'value'
        ? Number(p.amount) === Number(before.value)
        : Number(p.amount) === Number(before.percent)
    })
  return (
    assetClassId.value === s.asset_class.id &&
    manufacturerId.value === s.manufacturer.id &&
    model.value.trim() === s.model &&
    description.value.trim() === s.description &&
    sameList(keywords.value, s.keywords) &&
    Number(original) === Number(s.original_value) &&
    sameSpecs &&
    samePoints
  )
}

/** A new version only when the price itself changed (not just its photo or documents) */
const createsVersion = computed(() => {
  if (!isNewVersion.value) return false
  const points = typedPoints()
  const original = parseMoney(originalText.value, locale.value)
  return !points || !original || !sameAsSource(points, original)
})

/** Apply the photo and documents changed to the row; returns how to report what the server
 * refused (after the "saved" notice, so it is the one left on screen). */
async function saveMedia(rowId: number): Promise<() => void> {
  if (!hasMediaChanges(media.value)) return () => {}
  const problems = await applyMediaChanges(rowId, media.value)
  if (!problems.length) return () => {}
  const list = problems.map((p) => (p.name ? `${p.name}: ${p.reason}` : p.reason)).join(' · ')
  return () =>
    notifications.notify(t('averagePrices.media.applyError', { problems: list }), 'error')
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
  // Only the photo or documents changed: applied to the row, no new version
  if (props.source && isNewVersion.value && sameAsSource(points, original)) {
    try {
      if (!hasMediaChanges(media.value)) {
        notifications.notify(t('averagePrices.media.nothingChanged'))
      } else {
        const report = await saveMedia(props.source.id)
        emit('saved', null, 'media')
        report()
      }
      open.value = false
    } finally {
      saving.value = false
    }
    return
  }
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
      supersedes: isNewVersion.value ? props.source!.id : null,
    })
    // The photo and documents go to the row (the new version shares them)
    const report = await saveMedia(saved.id)
    emit('saved', saved, isNewVersion.value ? 'version' : isCopy.value ? 'copied' : 'created')
    report()
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

/** Who created the price (its first version) and who changed it last */
function priceAudit(price: AveragePrice | null | undefined) {
  return price
    ? {
        created_at: price.first_created_at,
        created_by_name: price.first_created_by_name,
        updated_at: price.updated_at,
        updated_by_name: price.updated_by_name,
      }
    : null
}
</script>

<template>
  <FormDialog
    :audit="isNewVersion ? priceAudit(source) : null"
    ref="formRef"
    v-model="open"
    :title="
      isNewVersion
        ? $t('averagePrices.newVersion')
        : isCopy
          ? $t('averagePrices.createCopy')
          : $t('averagePrices.new')
    "
    :subtitle="
      !source
        ? null
        : isCopy
          ? $t('averagePrices.copyOf', { name: `${source.manufacturer.name} ${source.model}` })
          : `${source.manufacturer.name} ${source.model}`
    "
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
        <v-tab value="media" prepend-icon="mdi-paperclip" data-testid="tab-media">
          {{ $t('averagePrices.formTabs.media') }}
          <v-badge
            v-if="hasMediaChanges(media)"
            dot
            inline
            color="warning"
            class="ml-1"
            :title="$t('averagePrices.media.pending')"
          />
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
              :vertical="scopeVertical"
              :sub-vertical="scopeSubVertical"
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
              @selected="manufacturerName = $event?.name ?? ''"
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
              <template #append-inner><WebSearchButton :term="modelSearchTerm" /></template>
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

      <!-- Photo and documents: the row's, applied when saved (never a new version) -->
      <v-window-item value="media" eager :transition="false" :reverse-transition="false">
        <PriceMediaTab
          v-model="media"
          :row-id="isNewVersion ? source!.id : null"
          :photo-id="isNewVersion ? (source!.photo_id ?? null) : null"
          :icon="assetClass?.icon ?? 'mdi-image-outline'"
          :title="photoSearchTerm"
        />
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
        {{ createsVersion ? $t('averagePrices.saveNewVersion') : $t('common.save') }}
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
