<script setup lang="ts">
/**
 * One scenario of an analysis (a tab): name, term, scope and its figures on top; below, the
 * grid of its assets (current average prices with quantities), which fills the rest of the
 * page — only the assets scroll. Every change asks the API for the scenario's figures
 * (`preview`); nothing is computed here. Assets whose curve stops before the term are flagged
 * (saving refuses them).
 */
import { useDateFormat } from '@/composables/useDateFormat'
import { computed, nextTick, onBeforeUnmount, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useValidationRules } from '@/composables/useValidationRules'
import { specSummary } from '@/modules/average-prices/specText'
import { currencySymbol, toInputMoney } from '@/utils/money'
import AssetCounts from './AssetCounts.vue'
import AveragePricePicker from './AveragePricePicker.vue'
import ScenarioTotalsBar from './ScenarioTotalsBar.vue'
import { previewScenario, type PricePosition, type ScenarioItem } from './api'
import {
  assetCounts,
  MAX_TERM,
  newKey,
  isEfmvInput,
  parseEfmvPercent,
  parseEfmvValue,
  parseServiceInput,
  parseTerm,
  parseUnitValue,
  scenarioInput,
  titleKey,
  type ItemDraft,
  type ScenarioDraft,
  type ScenarioErrors,
} from './draft'

const scenario = defineModel<ScenarioDraft>({ required: true })
const props = defineProps<{
  index: number
  errors?: ScenarioErrors
  /** Other scenarios' official names (`titleKey`: term + name; they must be different) */
  otherKeys: string[]
  /** This scenario's official name ("36 Months - Desktops") */
  title: string
  /** The assets it admits: the analysis's vertical (sub_vertical null = the whole vertical) */
  scope: { vertical: number | null; sub_vertical: number | null }
  /** "Industry / Yellow line": shown as a label (set by the wizard) */
  scopeLabel: string | null
}>()

const { t, n, locale } = useI18n()
// Dates in the formats the user chose (Settings)
const { d } = useDateFormat()
const rules = useValidationRules()

// Optional: the official name is the term + the name; it must be unique in the analysis
const nameRules = [
  rules.maxLength(100),
  (v: string) =>
    !props.otherKeys.includes(titleKey(scenario.value.term, v)) || t('efmv.scenario.nameTaken'),
]
// The term is part of the official name: check the name again when it changes
const nameField = ref<{ validate: () => Promise<string[]> } | null>(null)
watch(
  () => scenario.value.term,
  () => nameField.value?.validate(),
)

const termRules = [
  rules.required,
  (v: string) => parseTerm(v) !== null || t('efmv.scenario.termRange', { max: MAX_TERM }),
]
const quantityRules = [
  (v: number | string) =>
    (/^\d+$/.test(String(v)) && Number(v) >= 1) || t('efmv.scenario.quantityRule'),
]

// --- Figures from the API ----------------------------------------------------------------------

let timer: ReturnType<typeof setTimeout> | undefined
let request = 0
const pending = ref(false)

/** Item details by position in `items` (deleted prices have none). */
function detail(index: number): ScenarioItem | null {
  return scenario.value.preview?.items[index] ?? null
}

async function refresh() {
  const term = parseTerm(scenario.value.term)
  if (term === null) return
  const input = scenarioInput(scenario.value, locale.value)
  const current = ++request
  pending.value = true
  try {
    const preview = await previewScenario({
      term_months: term,
      vertical: props.scope.vertical,
      sub_vertical: props.scope.sub_vertical,
      items: input.items,
    })
    if (current !== request) return
    // Put the details back in the positions of `items` (deleted prices were not sent)
    const sent = [...preview.items]
    const old = scenario.value.preview?.items ?? []
    scenario.value.preview = {
      totals: preview.totals,
      has_expired: preview.has_expired,
      items: scenario.value.items.map((item, i) =>
        item.average_price === null
          ? (old[i] ?? deletedItem(item.quantity))
          : (sent.shift() ?? deletedItem(item.quantity)),
      ),
    }
  } catch {
    /* keep the figures shown; saving reports what is wrong */
  } finally {
    if (current === request) pending.value = false
  }
}

function deletedItem(quantity: number): ScenarioItem {
  return {
    id: null,
    quantity,
    unit_value: null,
    value_from_price: false,
    available: false,
    average_price: null,
    line_total: null,
    out_of_curve: false,
    expired: false,
  }
}

const watched = computed(() =>
  JSON.stringify([
    scenario.value.term,
    props.scope,
    scenario.value.items.map((i) => [
      i.average_price,
      i.quantity,
      i.unit_value,
      i.efmv_value,
      i.service,
    ]),
  ]),
)
watch(watched, () => {
  clearTimeout(timer)
  timer = setTimeout(refresh, 350)
})
onBeforeUnmount(() => clearTimeout(timer))

// --- Assets ------------------------------------------------------------------------------------

// The same asset may be in several rows (e.g. a different value per delivery state)

/** A new empty row: the asset is chosen in it (Asset column). */
function addRow() {
  scenario.value.items.push({
    key: newKey(),
    average_price: null,
    quantity: 1,
    unit_value: '',
    efmv_value: '',
    pending: true,
  })
  scenario.value.preview?.items.push({ ...deletedItem(1), available: true })
}

function chooseAsset(index: number, id: number) {
  const item = scenario.value.items[index]!
  item.average_price = id
  item.pending = false
  // Next: the value of this row (its field is enabled once the row has an asset)
  nextTick(() => focusCell(index, 'unit'))
  // The value is typed by the analyst (Average Prices only positions it); the details come
  // with the next preview
}

// --- Keyboard (spreadsheet-like) ---------------------------------------------------------------

const grid = ref<{ $el: HTMLElement } | null>(null)

/** Focus (and select) the field of a cell, when it can be edited. */
function focusCell(row: number, column: string) {
  const input = grid.value?.$el.querySelector<HTMLInputElement>(
    `tr[data-row="${row}"] td[data-col="${column}"] input:not([type="hidden"]):not(:disabled)`,
  )
  input?.focus()
  input?.select()
}

/**
 * Enter / ↓: same column, next row (Enter on the last row adds one); Shift+Enter / ↑: previous
 * row. The asset picker keeps Enter and the arrows for its own list.
 */
function onGridKeydown(event: KeyboardEvent) {
  const cell = (event.target as HTMLElement).closest<HTMLElement>('td[data-col]')
  const column = cell?.dataset.col
  if (!cell || !column || column === 'asset') return
  const row = Number(cell.closest<HTMLElement>('tr')?.dataset.row)
  let step = 0
  if (event.key === 'Enter') step = event.shiftKey ? -1 : 1
  else if (event.key === 'ArrowDown') step = 1
  else if (event.key === 'ArrowUp') step = -1
  if (!step) return
  event.preventDefault()
  if (event.key === 'Enter' && step === 1 && row === scenario.value.items.length - 1) {
    addRow() // its asset picker takes the focus
    return
  }
  focusCell(row + step, column)
}

/** The value as the UI shows money ("100.000,00" in pt-br) once the field is left. */
function tidyUnitValue(item: ItemDraft) {
  const value = parseUnitValue(item.unit_value, locale.value)
  if (value !== null) item.unit_value = toInputMoney(value, locale.value)
}
/**
 * Leaving the eFMV cell (Tab, Enter, click elsewhere): a value is shown as money; a percentage
 * ("25%") is turned into the value it gives — resolved by the API, as a % of the unit value.
 */
async function tidyEfmvValue(item: ItemDraft) {
  const value = parseEfmvValue(item.efmv_value, locale.value)
  if (value !== null) {
    item.efmv_value = toInputMoney(value, locale.value)
    return
  }
  const typed = item.efmv_value
  if (parseEfmvPercent(typed, locale.value) === null) return
  clearTimeout(timer)
  await refresh()
  const index = scenario.value.items.indexOf(item)
  const resolved = index >= 0 ? detail(index)?.efmv_value : null
  // Only if nothing was typed meanwhile
  if (resolved && item.efmv_value === typed) {
    item.efmv_value = toInputMoney(resolved, locale.value)
  }
}

function removeAsset(index: number) {
  const [removed] = scenario.value.items.splice(index, 1)
  scenario.value.preview?.items.splice(index, 1)
  if (removed) unselect(removed.key)
}

// --- Services (SV): at most one per asset, as a row under it ------------------------------------

function addService(item: ItemDraft) {
  if (item.service || item.average_price === null) return
  // Zero to start with, added to the asset; the name can be changed
  item.service = {
    name: t('efmv.service.defaultName'),
    value: toInputMoney('0', locale.value),
    mode: 'add',
  }
}

/** Removing a service: deducted, its value goes back to the asset (the API recomputes it) */
function removeService(item: ItemDraft) {
  item.service = null
  selected.value.delete(serviceRowId(item.key))
}

function toggleServiceMode(item: ItemDraft) {
  if (item.service) item.service.mode = item.service.mode === 'add' ? 'deduct' : 'add'
}

/** Leaving the service's value: money shown as money; "8%" turned into its value (by the API) */
async function tidyServiceValue(item: ItemDraft) {
  const service = item.service
  if (!service) return
  const parsed = parseServiceInput(service.value, locale.value)
  if (parsed && 'value' in parsed) {
    service.value = toInputMoney(parsed.value, locale.value)
    return
  }
  if (!parsed) return
  const typed = service.value
  clearTimeout(timer)
  await refresh()
  const index = scenario.value.items.indexOf(item)
  const resolved = index >= 0 ? detail(index)?.service?.value : null
  if (resolved && item.service?.value === typed) {
    item.service.value = toInputMoney(resolved, locale.value)
  }
}

const serviceValueRules = [
  (v: string) => parseServiceInput(v ?? '', locale.value) !== null || t('efmv.service.valueRule'),
]

// --- Selection: operations on several rows at once ---------------------------------------------

/** Selected rows: an asset ("a:<key>") or its service ("s:<key>") */
const selected = ref(new Set<string>())
const assetRowId = (key: number) => `a:${key}`
const serviceRowId = (key: number) => `s:${key}`

function unselect(key: number) {
  selected.value.delete(assetRowId(key))
  selected.value.delete(serviceRowId(key))
}

function toggleRow(id: string, on: boolean) {
  if (on) selected.value.add(id)
  else selected.value.delete(id)
}

/** Every row (assets and their services) */
const allRowIds = computed(() =>
  scenario.value.items.flatMap((i) =>
    i.service ? [assetRowId(i.key), serviceRowId(i.key)] : [assetRowId(i.key)],
  ),
)
const allSelected = computed(
  () => allRowIds.value.length > 0 && allRowIds.value.every((id) => selected.value.has(id)),
)
function toggleAll(on: boolean) {
  selected.value = new Set(on ? allRowIds.value : [])
}

/** Selected assets that can get a service (chosen, none yet) */
const canAddService = computed(() =>
  scenario.value.items.some(
    (i) => selected.value.has(assetRowId(i.key)) && !i.service && i.average_price !== null,
  ),
)

/** Remove what is selected: assets (with their services) and services alone */
function removeSelected() {
  for (let index = scenario.value.items.length - 1; index >= 0; index--) {
    const item = scenario.value.items[index]!
    if (selected.value.has(assetRowId(item.key))) removeAsset(index)
    else if (selected.value.has(serviceRowId(item.key))) removeService(item)
  }
  selected.value = new Set()
}

function addServiceToSelected() {
  for (const item of scenario.value.items) {
    if (selected.value.has(assetRowId(item.key))) addService(item)
  }
}

/** The errors of an item's service, whatever their shape */
function serviceErrors(index: number): string[] {
  const errors = props.errors?.items?.[String(index)]?.service
  if (!errors) return []
  return Array.isArray(errors) ? errors : Object.values(errors).flat()
}

const currency = computed(
  () => scenario.value.preview?.items.find((i) => i.currency)?.currency ?? 'BRL',
)
/** "R$": shown on the left of every money cell, the number on the right */
const symbol = computed(() => currencySymbol(currency.value, locale.value))

const itemError = (index: number) => {
  const errors = props.errors?.items?.[String(index)]
  return [
    ...(errors?.average_price ?? []),
    ...(errors?.quantity ?? []),
    ...(errors?.unit_value ?? []),
    ...(errors?.efmv_value ?? []),
  ]
}

// Empty: the average price's value counts (shown as the placeholder)
const unitValueRules = [
  (v: string) =>
    !v?.trim() || parseUnitValue(v, locale.value) !== null || t('efmv.item.unitValueRule'),
]
// Empty: the average price's curve at the term counts (shown as the placeholder)
const efmvValueRules = [
  (v: string) => isEfmvInput(v ?? '', locale.value) || t('efmv.item.efmvValueRule'),
]

const POSITION_COLORS: Record<PricePosition, string> = {
  below: 'error',
  slightly_below: 'warning',
  compatible: 'success',
  slightly_above: 'warning',
  above: 'error',
}
const POSITION_ICONS: Record<PricePosition, string> = {
  below: 'mdi-arrow-down-bold',
  slightly_below: 'mdi-arrow-bottom-right',
  compatible: 'mdi-check-bold',
  slightly_above: 'mdi-arrow-top-right',
  above: 'mdi-arrow-up-bold',
}

/** "-8,00%" / "+12,50%" in the UI language */
function signedPercent(value: string): string {
  const number = Number(value)
  return `${number > 0 ? '+' : ''}${n(number, 'percentValue')}%`
}

/** "Ultra 7 265U vPro, 32 GB, 14 Inches" */
const specsOf = (index: number) => specSummary(detail(index)?.specs ?? [], t, n)

const shortDate = (iso: string) => d(new Date(`${iso}T00:00:00`), 'short')
</script>

<template>
  <div class="scenario-panel" :data-testid="`scenario-${index}`">
    <div class="scenario-head pa-4 pb-2">
      <v-row dense>
        <v-col cols="12" lg="6">
          <div class="d-flex ga-2 mb-2">
            <v-text-field
              ref="nameField"
              v-model="scenario.name"
              :label="$t('efmv.scenario.name')"
              :hint="$t('efmv.scenario.nameHint', { title })"
              persistent-hint
              :rules="nameRules"
              :error-messages="errors?.name"
              maxlength="100"
              density="compact"
              class="flex-grow-1"
              data-testid="scenario-name"
            />
            <v-text-field
              v-model="scenario.term"
              :label="`${$t('efmv.scenario.term')} *`"
              :suffix="$t('efmv.scenario.months')"
              inputmode="numeric"
              :rules="termRules"
              :error-messages="errors?.term_months"
              density="compact"
              class="term"
              data-testid="scenario-term"
            />
          </div>
          <v-textarea
            v-model="scenario.scope"
            :label="$t('efmv.scenario.scope')"
            :placeholder="$t('efmv.scenario.scopeHint')"
            :error-messages="errors?.scope"
            rows="2"
            no-resize
            density="compact"
            hide-details="auto"
            data-testid="scenario-scope"
          />
        </v-col>
        <v-col cols="12" lg="6">
          <ScenarioTotalsBar
            :totals="scenario.preview?.totals ?? null"
            :currency="currency"
            :loading="pending"
          />
        </v-col>
      </v-row>
      <div class="d-flex flex-wrap align-center ga-3 mt-3">
        <div class="text-subtitle-2 mr-auto">
          {{ $t('efmv.scenario.assets') }}
          <!-- How many of each kind: HW, SW, SV -->
          <AssetCounts :counts="assetCounts(scenario.items)" class="ml-1" />
          <!-- The analysis's vertical (set by the wizard): the assets offered are of it -->
          <v-chip
            v-if="scopeLabel"
            size="small"
            variant="tonal"
            color="primary"
            label
            prepend-icon="mdi-shape-outline"
            class="ml-2"
            :title="$t('efmv.scenario.verticalHint')"
            data-testid="scenario-vertical"
          >
            {{ scopeLabel }}
          </v-chip>
        </div>
        <!-- Operations on the selected rows -->
        <template v-if="selected.size">
          <span class="text-body-2 text-medium-emphasis" data-testid="selected-count">
            {{ $t('efmv.selection.count', selected.size) }}
          </span>
          <v-btn
            variant="tonal"
            prepend-icon="mdi-wrench-outline"
            class="text-none"
            :disabled="!canAddService"
            :title="$t('efmv.selection.addServiceHint')"
            data-testid="add-service"
            @click="addServiceToSelected"
          >
            {{ $t('efmv.selection.addService') }}
          </v-btn>
          <v-btn
            variant="tonal"
            color="error"
            prepend-icon="mdi-delete-outline"
            class="text-none"
            data-testid="remove-selected"
            @click="removeSelected"
          >
            {{ $t('efmv.selection.remove') }}
          </v-btn>
        </template>
        <v-btn
          variant="tonal"
          color="primary"
          prepend-icon="mdi-plus"
          class="text-none"
          data-testid="add-row"
          @click="addRow"
        >
          {{ $t('efmv.scenario.addRow') }}
        </v-btn>
      </div>
    </div>

    <v-alert
      v-if="scenario.preview?.has_expired"
      type="warning"
      variant="tonal"
      density="compact"
      class="mx-4 mb-2 flex-shrink-0"
      data-testid="expired-warning"
    >
      {{ $t('efmv.item.expiredWarning') }}
    </v-alert>
    <!-- A spreadsheet-like grid: Tab goes through the cells (quantity → asset → unit value →
         eFMV),
         Enter and ↑/↓ move to the same column of the next/previous row -->
    <v-table
      ref="grid"
      density="compact"
      fixed-header
      class="assets sheet"
      data-testid="assets"
      @keydown="onGridKeydown"
    >
      <thead>
        <tr>
          <th class="cell-check">
            <v-checkbox-btn
              :model-value="allSelected"
              :indeterminate="selected.size > 0 && !allSelected"
              :disabled="!scenario.items.length"
              density="compact"
              :aria-label="$t('efmv.selection.all')"
              data-testid="select-all"
              @update:model-value="toggleAll(!!$event)"
            />
          </th>
          <th class="row-number">#</th>
          <th class="text-end" style="width: 84px">{{ $t('efmv.item.quantity') }}</th>
          <th style="min-width: 260px">{{ $t('efmv.item.asset') }}</th>
          <th class="text-end" style="width: 170px">{{ $t('efmv.item.unitValue') }}</th>
          <th
            class="text-end"
            style="width: 170px"
            :title="$t('efmv.item.efmvValueHint', { term: scenario.term })"
          >
            {{ $t('efmv.item.efmvValue') }}
          </th>
          <th class="text-end" style="width: 160px">{{ $t('efmv.item.total') }}</th>
          <th style="width: 40px"></th>
        </tr>
      </thead>
      <tbody>
        <tr v-if="!scenario.items.length">
          <td colspan="8" class="text-medium-emphasis text-center py-6">
            {{ $t('efmv.scenario.noAssets') }}
          </td>
        </tr>
        <template v-for="(item, i) in scenario.items" :key="item.key">
          <tr
            :data-row="i"
            :class="{
              'row-off':
                detail(i)?.out_of_curve || detail(i)?.out_of_scope || item.average_price === null,
            }"
            data-testid="asset-row"
          >
            <td class="cell-check">
              <v-checkbox-btn
                :model-value="selected.has(assetRowId(item.key))"
                density="compact"
                tabindex="-1"
                :aria-label="$t('efmv.selection.row')"
                data-testid="select-row"
                @update:model-value="toggleRow(assetRowId(item.key), !!$event)"
              />
            </td>
            <td class="row-number">{{ i + 1 }}</td>
            <td class="cell-input" data-col="quantity">
              <v-text-field
                v-model.number="item.quantity"
                inputmode="numeric"
                variant="plain"
                density="compact"
                hide-details
                class="text-end-input"
                :rules="item.average_price === null ? [] : quantityRules"
                :disabled="item.average_price === null"
                :aria-label="$t('efmv.item.quantity')"
                :title="$t('efmv.scenario.quantityRule')"
                data-testid="quantity"
              />
            </td>
            <td :class="item.pending ? 'cell-input' : 'cell-text'" data-col="asset">
              <AveragePricePicker
                v-if="item.pending"
                label=""
                :placeholder="$t('efmv.scenario.chooseAsset')"
                :vertical="scope.vertical"
                :sub-vertical="scope.sub_vertical"
                prepend-inner-icon="mdi-magnify"
                variant="plain"
                density="compact"
                hide-details
                autofocus
                data-testid="add-asset"
                @pick="chooseAsset(i, $event)"
              />
              <div
                v-else-if="detail(i)?.asset_class"
                class="d-flex align-center ga-2"
                :title="
                  [
                    `${detail(i)!.manufacturer} ${detail(i)!.model}`,
                    detail(i)!.asset_class!.name,
                    specsOf(i),
                  ]
                    .filter(Boolean)
                    .join(' · ')
                "
              >
                <v-icon :icon="detail(i)!.asset_class!.icon" size="18" color="primary" />
                <div class="asset-text">
                  <div class="text-truncate">
                    <span class="font-weight-medium">{{ detail(i)!.model }}</span>
                    <span class="text-medium-emphasis"> · {{ detail(i)!.manufacturer }}</span>
                  </div>
                  <div class="text-caption text-medium-emphasis text-truncate">
                    {{ detail(i)!.asset_class!.name }}
                    <template v-if="specsOf(i)"> · {{ specsOf(i) }}</template>
                    <template v-if="detail(i)!.priced_on">
                      ·
                      <span
                        v-if="detail(i)!.expired"
                        class="text-warning"
                        :title="
                          $t('efmv.item.expiredHint', {
                            date: shortDate(detail(i)!.priced_on!),
                            until: shortDate(detail(i)!.valid_until!),
                          })
                        "
                        data-testid="expired"
                      >
                        <v-icon icon="mdi-calendar-alert" size="x-small" />
                        {{ $t('efmv.item.expired') }}
                      </span>
                      <span v-else>
                        {{ $t('efmv.item.pricedOn', { date: shortDate(detail(i)!.priced_on!) }) }}
                      </span>
                    </template>
                  </div>
                </div>
              </div>
              <div
                v-else-if="item.average_price === null"
                class="text-medium-emphasis text-caption"
              >
                <v-icon icon="mdi-alert-outline" color="warning" size="small" class="mr-1" />
                {{ $t('efmv.item.deleted') }}
              </div>
              <v-progress-circular v-else indeterminate size="16" width="2" />
              <div
                v-if="detail(i)?.out_of_scope && !itemError(i).length"
                class="text-caption text-error"
                data-testid="out-of-scope"
              >
                <v-icon icon="mdi-alert-circle-outline" size="x-small" />
                {{ $t('efmv.item.outOfScope') }}
              </div>
              <div
                v-if="detail(i)?.out_of_curve && !itemError(i).length"
                class="text-caption text-error"
                data-testid="out-of-curve"
              >
                <v-icon icon="mdi-alert-circle-outline" size="x-small" />
                {{ $t('efmv.item.outOfCurve', { term: scenario.term }) }}
              </div>
              <div v-for="message in itemError(i)" :key="message" class="text-caption text-error">
                {{ message }}
              </div>
            </td>
            <!-- The value typed and, below it, how it compares with Average Prices -->
            <td class="cell-input money-cell" data-col="unit">
              <v-text-field
                v-model="item.unit_value"
                inputmode="decimal"
                :placeholder="
                  detail(i)?.original_value ? toInputMoney(detail(i)!.original_value!, locale) : ''
                "
                variant="plain"
                density="compact"
                hide-details
                class="text-end-input"
                :rules="item.average_price === null ? [] : unitValueRules"
                :disabled="item.average_price === null"
                :aria-label="$t('efmv.item.unitValue')"
                :title="
                  item.service?.mode === 'deduct' && detail(i)?.net_unit_value
                    ? $t('efmv.service.netHint', {
                        value: `${symbol} ${toInputMoney(detail(i)!.net_unit_value!, locale)}`,
                      })
                    : $t('efmv.item.unitValueHint')
                "
                data-testid="unit-value"
                @blur="tidyUnitValue(item)"
              >
                <!-- Always shown (a prefix only shows once there is a value) -->
                <template #prepend-inner
                  ><span class="symbol">{{ symbol }}</span></template
                >
              </v-text-field>
              <div class="chip-line">
                <v-chip
                  v-if="detail(i)?.position"
                  class="cell-chip"
                  :color="POSITION_COLORS[detail(i)!.position!]"
                  :prepend-icon="POSITION_ICONS[detail(i)!.position!]"
                  size="x-small"
                  variant="tonal"
                  label
                  :title="$t(`efmv.position.${detail(i)!.position}Hint`)"
                  data-testid="position"
                >
                  {{ $t(`efmv.position.${detail(i)!.position}`) }}
                  ({{ signedPercent(detail(i)!.variation_percent!) }})
                </v-chip>
              </div>
            </td>
            <!-- The eFMV and, below it, what it is of the unit value -->
            <td class="cell-input money-cell" data-col="efmv">
              <v-text-field
                v-model="item.efmv_value"
                inputmode="decimal"
                :placeholder="
                  detail(i)?.curve_value ? toInputMoney(detail(i)!.curve_value!, locale) : ''
                "
                variant="plain"
                density="compact"
                hide-details
                class="text-end-input"
                :rules="item.average_price === null ? [] : efmvValueRules"
                :disabled="item.average_price === null"
                :aria-label="$t('efmv.item.efmvValue')"
                :title="$t('efmv.item.efmvValueHint', { term: scenario.term })"
                data-testid="efmv-value"
                @blur="tidyEfmvValue(item)"
              >
                <!-- Always shown (a prefix only shows once there is a value) -->
                <template #prepend-inner
                  ><span class="symbol">{{ symbol }}</span></template
                >
              </v-text-field>
              <!-- Same look as the position below the unit value -->
              <div class="chip-line">
                <v-chip
                  v-if="detail(i)?.efmv_percent"
                  size="x-small"
                  variant="tonal"
                  label
                  class="cell-chip numeric"
                  :title="$t('efmv.item.efmvPercentHint')"
                  data-testid="efmv-percent"
                >
                  {{
                    $t('efmv.item.efmvPercent', {
                      percent: $n(Number(detail(i)!.efmv_percent), 'percentValue'),
                    })
                  }}
                </v-chip>
              </div>
            </td>
            <td
              class="money-cell text-no-wrap numeric font-weight-medium"
              :class="{ 'text-disabled': detail(i)?.out_of_curve || detail(i)?.out_of_scope }"
            >
              <div v-if="detail(i)?.line_total" class="money">
                <span class="symbol font-weight-regular">{{ symbol }}</span>
                <span data-testid="line-total">{{
                  toInputMoney(detail(i)!.line_total!, locale)
                }}</span>
              </div>
              <div v-else class="money justify-end">—</div>
              <!-- Its share of the scenario's LO, as the chips of the other columns -->
              <div class="chip-line">
                <v-chip
                  v-if="detail(i)?.weight_percent"
                  size="x-small"
                  variant="tonal"
                  label
                  class="cell-chip numeric font-weight-regular"
                  :title="$t('efmv.item.weightHint')"
                  data-testid="weight"
                >
                  {{
                    $t('efmv.item.weightPercent', {
                      percent: $n(Number(detail(i)!.weight_percent), 'percentValue'),
                    })
                  }}
                </v-chip>
              </div>
            </td>
            <td class="cell-action">
              <v-btn
                icon="mdi-close"
                variant="text"
                size="x-small"
                tabindex="-1"
                class="remove"
                :title="$t('efmv.item.remove')"
                :aria-label="$t('efmv.item.remove')"
                data-testid="remove-asset"
                @click="removeAsset(i)"
              />
            </td>
          </tr>
          <!-- Its service (SV): per unit, the asset's quantity; eFMV 0 -->
          <tr
            v-if="item.service"
            class="service-row"
            :class="{ 'row-off': detail(i)?.service?.too_high }"
            data-testid="service-row"
          >
            <td class="cell-check">
              <v-checkbox-btn
                :model-value="selected.has(serviceRowId(item.key))"
                density="compact"
                tabindex="-1"
                :aria-label="$t('efmv.selection.row')"
                data-testid="select-service"
                @update:model-value="toggleRow(serviceRowId(item.key), !!$event)"
              />
            </td>
            <td class="row-number">
              <v-icon icon="mdi-subdirectory-arrow-right" size="small" />
            </td>
            <td
              class="cell-text text-end numeric text-medium-emphasis"
              data-testid="service-quantity"
            >
              {{ item.quantity }}
            </td>
            <td class="cell-input" data-col="service-name">
              <v-text-field
                v-model="item.service.name"
                variant="plain"
                density="compact"
                hide-details
                maxlength="100"
                :rules="[(v: string) => !!v?.trim() || t('validation.required')]"
                :aria-label="$t('efmv.service.name')"
                data-testid="service-name"
              >
                <template #prepend-inner>
                  <v-chip size="x-small" label color="secondary" variant="tonal" class="mr-1">
                    {{ $t('efmv.service.sv') }}
                  </v-chip>
                </template>
              </v-text-field>
              <div
                v-for="message in [
                  ...(detail(i)?.service?.too_high && !serviceErrors(i).length
                    ? [$t('efmv.service.tooHigh')]
                    : []),
                  ...serviceErrors(i),
                ]"
                :key="message"
                class="text-caption text-error px-3 pb-1"
                data-testid="service-error"
              >
                {{ message }}
              </div>
            </td>
            <!-- Its value (money or "8%") and whether it is added to the asset or deducted -->
            <td class="cell-input money-cell" data-col="service-value">
              <v-text-field
                v-model="item.service.value"
                inputmode="decimal"
                variant="plain"
                density="compact"
                hide-details
                class="text-end-input"
                :rules="serviceValueRules"
                :aria-label="$t('efmv.service.value')"
                :title="$t('efmv.service.valueHint')"
                data-testid="service-value"
                @blur="tidyServiceValue(item)"
              >
                <template #prepend-inner
                  ><span class="symbol">{{ symbol }}</span></template
                >
              </v-text-field>
              <div class="chip-line">
                <v-chip
                  class="cell-chip"
                  size="x-small"
                  variant="tonal"
                  label
                  :color="item.service.mode === 'deduct' ? 'warning' : 'primary'"
                  :prepend-icon="item.service.mode === 'deduct' ? 'mdi-minus' : 'mdi-plus'"
                  :title="$t('efmv.service.modeHint')"
                  data-testid="service-mode"
                  @click="toggleServiceMode(item)"
                >
                  {{ $t(`efmv.service.${item.service.mode}`) }}
                </v-chip>
              </div>
            </td>
            <!-- Services are not resold: no eFMV -->
            <td
              class="money-cell text-no-wrap numeric text-medium-emphasis"
              :title="$t('efmv.service.efmvHint')"
            >
              <div class="money" data-testid="service-efmv">
                <span class="symbol">{{ symbol }}</span>
                <span>{{ toInputMoney('0', locale) }}</span>
              </div>
              <div class="chip-line" />
            </td>
            <td class="money-cell text-no-wrap numeric font-weight-medium">
              <div v-if="detail(i)?.service && !detail(i)!.service!.too_high" class="money">
                <span class="symbol font-weight-regular">{{ symbol }}</span>
                <span data-testid="service-total">{{
                  toInputMoney(detail(i)!.service!.line_total, locale)
                }}</span>
              </div>
              <div v-else class="money justify-end">—</div>
              <div class="chip-line">
                <v-chip
                  v-if="detail(i)?.service?.weight_percent"
                  size="x-small"
                  variant="tonal"
                  label
                  class="cell-chip numeric font-weight-regular"
                  :title="$t('efmv.item.weightHint')"
                  data-testid="service-weight"
                >
                  {{
                    $t('efmv.item.weightPercent', {
                      percent: $n(Number(detail(i)!.service!.weight_percent), 'percentValue'),
                    })
                  }}
                </v-chip>
              </div>
            </td>
            <td class="cell-action">
              <v-btn
                icon="mdi-close"
                variant="text"
                size="x-small"
                tabindex="-1"
                class="remove"
                :title="$t('efmv.service.remove')"
                :aria-label="$t('efmv.service.remove')"
                data-testid="remove-service"
                @click="removeService(item)"
              />
            </td>
          </tr>
        </template>
      </tbody>
    </v-table>
  </div>
</template>

<style scoped>
.scenario-panel {
  display: flex;
  flex-direction: column;
}
.term {
  flex: 0 0 150px;
}
.assets {
  border-top: thin solid rgba(var(--v-border-color), var(--v-border-opacity));
}

/* --- Spreadsheet look ------------------------------------------------------------------------- */
.sheet {
  --cell-border: rgba(var(--v-border-color), var(--v-border-opacity));
  --cell-height: 46px;
}
.sheet :deep(th),
.sheet :deep(td) {
  border-right: thin solid var(--cell-border);
  border-bottom: thin solid var(--cell-border) !important;
  vertical-align: middle;
  padding: 0 10px !important;
  height: var(--cell-height) !important;
}
.sheet :deep(th:last-child),
.sheet :deep(td:last-child) {
  border-right: 0;
}
.sheet :deep(thead th) {
  /* A tint over the surface, so the rows scroll under an opaque header */
  background:
    linear-gradient(rgba(var(--v-theme-on-surface), 0.06), rgba(var(--v-theme-on-surface), 0.06)),
    rgb(var(--v-theme-surface)) !important;
  font-weight: 600;
  white-space: nowrap;
}
/* Selection: a narrow first column */
.sheet :deep(th.cell-check),
.sheet :deep(td.cell-check) {
  width: 40px;
  padding: 0 4px !important;
}
/* Service rows: a light tint, under their asset */
.sheet tbody tr.service-row > td:not(.row-number) {
  background: rgba(var(--v-theme-secondary), 0.04);
}
.row-number {
  width: 44px;
  text-align: center;
  color: rgba(var(--v-theme-on-surface), var(--v-medium-emphasis-opacity));
  background: rgba(var(--v-theme-on-surface), 0.04);
  font-variant-numeric: tabular-nums;
}
.sheet tbody tr:hover > td:not(.row-number) {
  background: rgba(var(--v-theme-primary), 0.04);
}
.sheet tbody tr.row-off > td:not(.row-number) {
  background: rgba(var(--v-theme-on-surface), 0.03);
}
.numeric {
  font-variant-numeric: tabular-nums;
}
.asset-text {
  min-width: 0;
  line-height: 1.25;
}

/* Editable cells: the field fills the cell; the cell shows focus and errors */
.sheet td.cell-input {
  padding: 0 !important;
}
.sheet td.cell-input:focus-within {
  box-shadow: inset 0 0 0 2px rgb(var(--v-theme-primary));
}
.sheet td.cell-input:has(.v-input--error) {
  box-shadow: inset 0 0 0 2px rgb(var(--v-theme-error));
  background: rgba(var(--v-theme-error), 0.06);
}
.cell-input :deep(.v-field) {
  padding-inline: 10px;
}
.cell-input :deep(.v-field__input) {
  min-height: var(--cell-height);
  padding-top: 0;
  padding-bottom: 0;
}
/* Fields use the same font size as the rest of the grid (Vuetify fields are larger) */
.sheet :deep(.v-field),
.sheet :deep(.v-field input),
.sheet .symbol {
  font-size: 0.875rem;
}
.text-end-input :deep(input) {
  text-align: right;
  font-variant-numeric: tabular-nums;
}

/*
 * Money cells (Unit Value, eFMV, Total) share one layout so their lines match across the row:
 * the value (currency symbol on the left, number on the right) on a line of fixed height, then
 * a line of fixed height for its chip (position, % of the unit value, weight).
 */
.sheet {
  --value-height: 28px;
  --chip-line-height: 24px;
}
.sheet td.money-cell {
  padding: 6px 0 !important;
}
.money-cell :deep(.v-field__input) {
  min-height: var(--value-height);
}
.money {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  height: var(--value-height);
  padding-inline: 10px;
}
.chip-line {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  height: var(--chip-line-height);
  padding-inline: 10px;
}
.cell-chip {
  height: 20px !important;
}
.symbol {
  color: rgba(var(--v-theme-on-surface), var(--v-medium-emphasis-opacity));
  white-space: nowrap;
}
.cell-input :deep(.v-field__prepend-inner) {
  align-items: center;
  padding-top: 0;
}

/* Remove: only on the row under the mouse (or with keyboard focus) */
.sheet td.cell-action {
  padding: 0 4px !important;
}
.remove {
  opacity: 0;
}
.sheet tbody tr:hover .remove,
.remove:focus-visible {
  opacity: 1;
}
/* Only the assets scroll, under the fixed column titles: on wide screens the grid takes the
   rest of the window; on narrow ones it has a height of its own */
.assets :deep(.v-table__wrapper) {
  max-height: calc(60vh / var(--ui-zoom, 1));
  overflow-y: auto;
}
@media (min-width: 960px) {
  .scenario-panel {
    height: 100%;
    min-height: 0;
  }
  .assets {
    flex: 1 1 0;
    min-height: 0;
    display: flex;
    flex-direction: column;
  }
  .assets :deep(.v-table__wrapper) {
    flex: 1 1 0;
    min-height: 0;
    max-height: none;
  }
}
</style>
