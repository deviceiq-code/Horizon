<script setup lang="ts">
/**
 * One scenario of an analysis (a tab): name, term, scope and its figures on top; below, the
 * grid of its assets (current average prices with quantities), which fills the rest of the
 * page — only the assets scroll. Every change asks the API for the scenario's figures
 * (`preview`); nothing is computed here. Assets whose curve stops before the term are flagged
 * (saving refuses them).
 */
import { computed, nextTick, onBeforeUnmount, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useValidationRules } from '@/composables/useValidationRules'
import { specSummary } from '@/modules/average-prices/specText'
import { formatMoney, toInputMoney } from '@/utils/money'
import AveragePricePicker from './AveragePricePicker.vue'
import VerticalScopePicker, { type VerticalScope } from './VerticalScopePicker.vue'
import ScenarioTotalsBar from './ScenarioTotalsBar.vue'
import { previewScenario, type PricePosition, type ScenarioItem } from './api'
import {
  MAX_TERM,
  newKey,
  parseEfmvValue,
  parseTerm,
  parseUnitValue,
  scenarioInput,
  type ItemDraft,
  type ScenarioDraft,
  type ScenarioErrors,
} from './draft'

const scenario = defineModel<ScenarioDraft>({ required: true })
const props = defineProps<{
  index: number
  canRemove: boolean
  errors?: ScenarioErrors
  /** Other scenarios' names (they must be different) */
  otherNames: string[]
}>()
const emit = defineEmits<{ remove: []; duplicate: [] }>()

const { t, n, d, locale } = useI18n()
const rules = useValidationRules()

const nameRules = [
  rules.required,
  rules.maxLength(100),
  (v: string) =>
    !props.otherNames.some((n) => n.trim().toLowerCase() === v.trim().toLowerCase()) ||
    t('efmv.scenario.nameTaken'),
]
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
      vertical: input.vertical,
      sub_vertical: input.sub_vertical,
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
    scenario.value.vertical,
    scenario.value.sub_vertical,
    scenario.value.items.map((i) => [i.average_price, i.quantity, i.unit_value, i.efmv_value]),
  ]),
)
watch(watched, () => {
  clearTimeout(timer)
  timer = setTimeout(refresh, 350)
})
onBeforeUnmount(() => clearTimeout(timer))

// --- Assets ------------------------------------------------------------------------------------

const chosen = computed(() =>
  scenario.value.items.map((i) => i.average_price).filter((id): id is number => id !== null),
)

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
function tidyEfmvValue(item: ItemDraft) {
  const value = parseEfmvValue(item.efmv_value, locale.value)
  if (value !== null) item.efmv_value = toInputMoney(value, locale.value)
}

function removeAsset(index: number) {
  scenario.value.items.splice(index, 1)
  scenario.value.preview?.items.splice(index, 1)
}

const currency = computed(
  () => scenario.value.preview?.items.find((i) => i.currency)?.currency ?? 'BRL',
)

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
  (v: string) =>
    !v?.trim() || parseEfmvValue(v, locale.value) !== null || t('efmv.item.efmvValueRule'),
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

/** The scenario's vertical / sub-vertical, as the picker edits it */
const verticalScope = computed<VerticalScope>({
  get: () => ({ vertical: scenario.value.vertical, sub_vertical: scenario.value.sub_vertical }),
  set: (value) => {
    scenario.value.vertical = value.vertical
    scenario.value.sub_vertical = value.sub_vertical
  },
})

/** "Ultra 7 265U vPro, 32 GB, 14 Inches" */
const specsOf = (index: number) => specSummary(detail(index)?.specs ?? [], t, n)

const shortDate = (iso: string) => d(new Date(`${iso}T00:00:00`), 'short')
</script>

<template>
  <div class="scenario-panel" :data-testid="`scenario-${index}`">
    <div class="scenario-head pa-4 pb-2">
      <v-row dense>
        <v-col cols="12" lg="6">
          <div class="d-flex ga-2">
            <v-text-field
              v-model="scenario.name"
              :label="`${$t('efmv.scenario.name')} *`"
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
            <div class="d-flex pt-1">
              <v-btn
                icon="mdi-content-copy"
                variant="text"
                size="small"
                :title="$t('efmv.scenario.duplicate')"
                :aria-label="$t('efmv.scenario.duplicate')"
                data-testid="duplicate-scenario"
                @click="emit('duplicate')"
              />
              <v-btn
                icon="mdi-delete-outline"
                variant="text"
                size="small"
                color="error"
                :disabled="!canRemove"
                :title="$t(canRemove ? 'efmv.scenario.remove' : 'efmv.scenario.keepOne')"
                :aria-label="$t('efmv.scenario.remove')"
                data-testid="remove-scenario"
                @click="emit('remove')"
              />
            </div>
          </div>
          <VerticalScopePicker
            v-model="verticalScope"
            :label="`${$t('efmv.scenario.vertical')} *`"
            :current-label="scenario.scope_label"
            :rules="[() => scenario.vertical !== null || t('validation.required')]"
            :error-messages="[...(errors?.vertical ?? []), ...(errors?.sub_vertical ?? [])]"
            :hint="$t('efmv.scenario.verticalHint')"
            density="compact"
            class="mb-1"
            data-testid="scenario-vertical"
          />
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
          <v-chip size="x-small" variant="tonal" class="ml-1" data-testid="asset-count">
            {{ scenario.items.length }}
          </v-chip>
        </div>
        <v-btn
          variant="tonal"
          color="primary"
          prepend-icon="mdi-plus"
          class="text-none"
          :disabled="scenario.vertical === null"
          :title="scenario.vertical === null ? $t('efmv.scenario.pickVerticalFirst') : undefined"
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
          <th class="row-number">#</th>
          <th class="text-end" style="width: 84px">{{ $t('efmv.item.quantity') }}</th>
          <th style="min-width: 260px">{{ $t('efmv.item.asset') }}</th>
          <th class="text-end" style="width: 170px">{{ $t('efmv.item.unitValue') }}</th>
          <th style="width: 210px">{{ $t('efmv.item.position') }}</th>
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
        <tr
          v-for="(item, i) in scenario.items"
          :key="item.key"
          :data-row="i"
          :class="{
            'row-off':
              detail(i)?.out_of_curve || detail(i)?.out_of_scope || item.average_price === null,
          }"
          data-testid="asset-row"
        >
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
              :exclude="chosen"
              :vertical="scenario.vertical"
              :sub-vertical="scenario.sub_vertical"
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
            <div v-else-if="item.average_price === null" class="text-medium-emphasis text-caption">
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
          <td class="cell-input" data-col="unit">
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
              :title="$t('efmv.item.unitValueHint')"
              data-testid="unit-value"
              @blur="tidyUnitValue(item)"
            />
          </td>
          <td class="cell-text">
            <v-chip
              v-if="detail(i)?.position"
              :color="POSITION_COLORS[detail(i)!.position!]"
              :prepend-icon="POSITION_ICONS[detail(i)!.position!]"
              size="small"
              variant="tonal"
              label
              :title="$t(`efmv.position.${detail(i)!.position}Hint`)"
              data-testid="position"
            >
              {{ $t(`efmv.position.${detail(i)!.position}`) }}
              ({{ signedPercent(detail(i)!.variation_percent!) }})
            </v-chip>
            <span v-else class="text-disabled">—</span>
          </td>
          <td class="cell-input" data-col="efmv">
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
            />
          </td>
          <td
            class="cell-text text-end text-no-wrap numeric font-weight-medium"
            :class="{ 'text-disabled': detail(i)?.out_of_curve || detail(i)?.out_of_scope }"
          >
            {{
              detail(i)?.line_total ? formatMoney(detail(i)!.line_total!, currency, locale) : '—'
            }}
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
.text-end-input :deep(input) {
  text-align: right;
  font-variant-numeric: tabular-nums;
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
  max-height: 60vh;
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
