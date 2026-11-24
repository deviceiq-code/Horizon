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
import { usePreferencesStore } from '@/stores/preferences'
import { useI18n } from 'vue-i18n'
import { useNumberFormat } from '@/composables/useNumberFormat'
import { useValidationRules } from '@/composables/useValidationRules'
import { specSummary } from '@/modules/average-prices/specText'
import { currencySymbol, toInputMoney } from '@/utils/money'
import AssetCounts from './AssetCounts.vue'
import AveragePricePicker from './AveragePricePicker.vue'
import ScenarioTotalsBar from './ScenarioTotalsBar.vue'
import { previewScenario, type ItemKind, type PricePosition, type ScenarioItem } from './api'
import {
  ATTACHMENTS,
  assetCounts,
  isDeleted,
  isStandalone,
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
  type AttachmentKey,
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

const { t, locale } = useI18n()
const { n } = useNumberFormat()
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
  const input = scenarioInput(
    scenario.value,
    locale.value,
    t('efmv.service.defaultName'),
    t('efmv.software.defaultName'),
  )
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
    scenario.value.suggestion = preview.scope_suggestion ?? ''
    scenario.value.preview = {
      totals: preview.totals,
      has_expired: preview.has_expired,
      scope_suggestion: preview.scope_suggestion,
      items: scenario.value.items.map((item, i) =>
        !isStandalone(item) && item.average_price === null
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
      i.kind,
      i.description,
      i.average_price,
      i.quantity,
      i.unit_value,
      i.efmv_value,
      i.service,
      i.software,
    ]),
  ]),
)
watch(watched, () => {
  clearTimeout(timer)
  timer = setTimeout(refresh, 350)
})
onBeforeUnmount(() => clearTimeout(timer))

// --- Smart Tools: the scope written from the assets ---------------------------------------------

const preferences = usePreferencesStore()

/**
 * The scope written from the assets is the field's placeholder (in gray): an empty scope means
 * that text, which follows the assets; what the analyst types is theirs and never changed.
 */
const scopeSuggestion = computed(() => (preferences.autoScope ? scenario.value.suggestion : ''))

/** The wand: the text written from the assets into the field, to edit it */
function writeScope() {
  scenario.value.scope = scopeSuggestion.value
}

// --- Assets ------------------------------------------------------------------------------------

// The same asset may be in several rows (e.g. a different value per delivery state)

/**
 * A new row: hardware — the asset is chosen in it (Asset column) — or software / a service of
 * its own (a description; empty: "Software" / "Service").
 */
function addRow(kind: ItemKind = 'hw') {
  const standalone = kind !== 'hw'
  scenario.value.items.push({
    key: newKey(),
    kind,
    description: '',
    average_price: null,
    quantity: 1,
    unit_value: '',
    efmv_value: '',
    pending: !standalone,
  })
  scenario.value.preview?.items.push({ ...deletedItem(1), kind, available: true })
  if (standalone) {
    const index = scenario.value.items.length - 1
    nextTick(() => focusCell(index, 'description'))
  }
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
  if (!cell || !column || column === 'asset' || !cell.closest('tr')?.dataset.row) return
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

/**
 * A service deducted from the asset leaves it worth less: the field shows that (the value the
 * API gives) while it is not being edited; editing shows the value typed again.
 */
const editingUnit = ref<number | null>(null)
function netShown(item: ItemDraft, index: number): boolean {
  const deducted = ATTACHMENTS.some(
    (key) =>
      item[key]?.mode === 'deduct' && !!detail(index)?.[key] && !detail(index)![key]!.too_high,
  )
  return deducted && !!detail(index)?.net_unit_value && editingUnit.value !== item.key
}
function unitShown(item: ItemDraft, index: number): string {
  return netShown(item, index)
    ? toInputMoney(detail(index)!.net_unit_value!, locale.value)
    : item.unit_value
}
function onUnitBlur(item: ItemDraft) {
  editingUnit.value = null
  tidyUnitValue(item)
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

// --- Attached software (SW) and service (SV): at most one of each per hardware line ---------

function attach(item: ItemDraft, key: AttachmentKey) {
  if (item[key] || isStandalone(item) || item.average_price === null) return
  // Zero to start with, added to the asset; no name: the placeholder ("Service" / "Software")
  item[key] = {
    name: '',
    value: toInputMoney('0', locale.value),
    mode: 'add',
    ...(key === 'software' && { efmv: '' }),
  }
}

/** Removing an attachment: deducted, its value goes back to the asset (the API recomputes it) */
function detach(item: ItemDraft, key: AttachmentKey) {
  item[key] = null
  if (selected.value === attachmentRowId(key, item.key)) selected.value = assetRowId(item.key)
}

function toggleMode(item: ItemDraft, key: AttachmentKey) {
  const attachment = item[key]
  if (attachment) attachment.mode = attachment.mode === 'add' ? 'deduct' : 'add'
}

/** Leaving an attachment's value: money shown as money; "8%" turned into its value (by the API) */
async function tidyAttachmentValue(item: ItemDraft, key: AttachmentKey) {
  const attachment = item[key]
  if (!attachment) return
  const parsed = parseServiceInput(attachment.value, locale.value)
  if (parsed && 'value' in parsed) {
    attachment.value = toInputMoney(parsed.value, locale.value)
    return
  }
  if (!parsed) return
  const typed = attachment.value
  clearTimeout(timer)
  await refresh()
  const index = scenario.value.items.indexOf(item)
  const resolved = index >= 0 ? detail(index)?.[key]?.value : null
  if (resolved && item[key]?.value === typed) {
    item[key]!.value = toInputMoney(resolved, locale.value)
  }
}

/** Leaving the attached software's eFMV: as the eFMV cells ("10%" → its value, by the API) */
async function tidySoftwareEfmv(item: ItemDraft) {
  const software = item.software
  if (!software) return
  const value = parseEfmvValue(software.efmv ?? '', locale.value)
  if (value !== null) {
    software.efmv = toInputMoney(value, locale.value)
    return
  }
  const typed = software.efmv ?? ''
  if (parseEfmvPercent(typed, locale.value) === null) return
  clearTimeout(timer)
  await refresh()
  const index = scenario.value.items.indexOf(item)
  const resolved = index >= 0 ? detail(index)?.software?.efmv_value : null
  if (resolved && item.software?.efmv === typed) {
    item.software.efmv = toInputMoney(resolved, locale.value)
  }
}

const serviceValueRules = [
  (v: string) => parseServiceInput(v ?? '', locale.value) !== null || t('efmv.service.valueRule'),
]

// --- Selection: one row at a time (click it; right-click opens its menu) ---------------------

/** The selected row: a line ("a:<key>"), its service ("s:<key>") or its software ("w:<key>") */
const selected = ref<string | null>(null)
const assetRowId = (key: number) => `a:${key}`
const ROW_PREFIX: Record<AttachmentKey, string> = { service: 's', software: 'w' }
const attachmentRowId = (attachment: AttachmentKey, key: number) =>
  `${ROW_PREFIX[attachment]}:${key}`

function unselect(key: number) {
  if (selected.value?.endsWith(`:${key}`)) selected.value = null
}

/** The selected row's item, and which attachment the row is (null: the line itself) */
const selection = computed(() => {
  if (!selected.value) return null
  const [prefix, key] = selected.value.split(':')
  const index = scenario.value.items.findIndex((i) => i.key === Number(key))
  if (index < 0) return null
  const attachment = (Object.keys(ROW_PREFIX) as AttachmentKey[]).find(
    (k) => ROW_PREFIX[k] === prefix,
  )
  return { index, item: scenario.value.items[index]!, attachment: attachment ?? null }
})

/** The selected hardware line can get this attachment (it has none of that kind yet) */
function canAttach(key: AttachmentKey) {
  const current = selection.value
  return (
    !!current &&
    !current.attachment &&
    !isStandalone(current.item) &&
    current.item.average_price !== null &&
    !current.item[key]
  )
}
const canAttachAny = computed(() => canAttach('software') || canAttach('service'))

function attachToSelected(key: AttachmentKey) {
  if (canAttach(key)) attach(selection.value!.item, key)
}

/** Remove the selected row: a line (with what is attached to it) or only an attachment */
function removeSelected() {
  const current = selection.value
  if (!current) return
  if (current.attachment) detach(current.item, current.attachment)
  else removeAsset(current.index)
  selected.value = null
}

// The row's menu (right click): the grid's toolbar options for that row
const menu = ref({ open: false, x: 0, y: 0 })
function openMenu(event: MouseEvent, rowId: string) {
  selected.value = rowId
  menu.value = { open: true, x: event.clientX, y: event.clientY }
}

/** The errors of an item's attachment, whatever their shape */
function attachmentErrors(index: number, key: AttachmentKey): string[] {
  const errors = props.errors?.items?.[String(index)]?.[key]
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

// Software / services of their own: a value is required
const requiredValueRules = [
  (v: string) => parseUnitValue(v ?? '', locale.value) !== null || t('efmv.item.unitValueRule'),
]
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

/** Icons and colors of the kinds (as the HW / SW / SV panel) */
const KIND_LOOK: Record<ItemKind, { icon: string; color: string }> = {
  hw: { icon: 'mdi-desktop-tower-monitor', color: 'primary' },
  sw: { icon: 'mdi-application-brackets-outline', color: 'info' },
  sv: { icon: 'mdi-wrench-outline', color: 'warning' },
}
const ATTACHMENT_KIND: Record<AttachmentKey, ItemKind> = { software: 'sw', service: 'sv' }
const defaultName = (kind: ItemKind) =>
  kind === 'sw' ? t('efmv.software.defaultName') : t('efmv.service.defaultName')
</script>

<template>
  <div class="scenario-panel" :data-testid="`scenario-${index}`">
    <div class="scenario-head pa-4 pb-2">
      <!-- Two rows lined up: name and term beside LO and eFMV at EOL; the scope beside the
           HW / SW / SV shares -->
      <div class="head-grid">
        <div class="d-flex ga-2 head-name">
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
        <ScenarioTotalsBar
          :totals="scenario.preview?.totals ?? null"
          :currency="currency"
          :loading="pending"
          class="head-main"
        />
        <v-textarea
          v-model="scenario.scope"
          :label="$t('efmv.scenario.scope')"
          :placeholder="scopeSuggestion || $t('efmv.scenario.scopeHint')"
          persistent-placeholder
          :error-messages="errors?.scope"
          rows="2"
          no-resize
          density="compact"
          hide-details="auto"
          class="head-scope"
          data-testid="scenario-scope"
        >
          <!-- Smart Tools: write it from the assets -->
          <template #append-inner>
            <v-btn
              icon="mdi-auto-fix"
              variant="text"
              size="small"
              density="comfortable"
              color="primary"
              :disabled="!scopeSuggestion || scenario.scope === scopeSuggestion"
              :title="$t('efmv.scenario.scopeWrite')"
              :aria-label="$t('efmv.scenario.scopeWrite')"
              data-testid="scope-write"
              @click="writeScope"
            />
          </template>
        </v-textarea>
        <ScenarioTotalsBar
          :totals="scenario.preview?.totals ?? null"
          :currency="currency"
          :loading="pending"
          part="shares"
          class="head-shares"
        />
      </div>
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
        <!-- On the selected row (click a row to select it; right click: the same options) -->
        <!-- Attach software or a service to the selected hardware line -->
        <v-menu location="bottom end">
          <template #activator="{ props: activator }">
            <v-btn
              v-bind="activator"
              variant="tonal"
              prepend-icon="mdi-link-variant"
              append-icon="mdi-menu-down"
              class="text-none"
              :disabled="!canAttachAny"
              :title="$t('efmv.selection.attachHint')"
              data-testid="attach"
            >
              {{ $t('efmv.selection.attach') }}
            </v-btn>
          </template>
          <v-list density="compact" min-width="200">
            <v-list-item
              v-for="key in ATTACHMENTS"
              :key="key"
              :prepend-icon="KIND_LOOK[ATTACHMENT_KIND[key]].icon"
              :title="$t(`efmv.selection.attach_${key}`)"
              :disabled="!canAttach(key)"
              :data-testid="`attach-${key}`"
              @click="attachToSelected(key)"
            />
          </v-list>
        </v-menu>
        <v-btn
          variant="tonal"
          color="error"
          prepend-icon="mdi-delete-outline"
          class="text-none"
          :disabled="!selection"
          :title="$t('efmv.selection.removeHint')"
          data-testid="remove-selected"
          @click="removeSelected"
        >
          {{ $t('efmv.selection.remove') }}
        </v-btn>
        <!-- A new line: hardware, software or a service -->
        <v-menu location="bottom end">
          <template #activator="{ props: activator }">
            <v-btn
              v-bind="activator"
              variant="tonal"
              color="primary"
              append-icon="mdi-menu-down"
              class="text-none"
              data-testid="add-row"
            >
              {{ $t('efmv.scenario.addRow') }}
            </v-btn>
          </template>
          <v-list density="compact" min-width="200">
            <v-list-item
              v-for="kind in ['hw', 'sw', 'sv'] as const"
              :key="kind"
              :prepend-icon="KIND_LOOK[kind].icon"
              :title="$t(`efmv.kinds.${kind}`)"
              :data-testid="`add-row-${kind}`"
              @click="addRow(kind)"
            />
          </v-list>
        </v-menu>
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
          <th
            class="text-end"
            style="width: 170px"
            :title="$t('efmv.item.efmvValueHint', { term: scenario.term })"
          >
            {{ $t('efmv.item.efmvValue') }}
          </th>
          <th class="text-end" style="width: 160px">{{ $t('efmv.item.total') }}</th>
        </tr>
      </thead>
      <tbody>
        <tr v-if="!scenario.items.length">
          <td colspan="6" class="text-medium-emphasis text-center py-6">
            {{ $t('efmv.scenario.noAssets') }}
          </td>
        </tr>
        <template v-for="(item, i) in scenario.items" :key="item.key">
          <tr
            :data-row="i"
            :class="{
              'row-off': detail(i)?.out_of_curve || detail(i)?.out_of_scope || isDeleted(item),
              'row-selected': selected === assetRowId(item.key),
            }"
            :aria-selected="selected === assetRowId(item.key)"
            data-testid="asset-row"
            @click="selected = assetRowId(item.key)"
            @contextmenu.prevent="openMenu($event, assetRowId(item.key))"
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
                :rules="isDeleted(item) || item.pending ? [] : quantityRules"
                :disabled="isDeleted(item) || !!item.pending"
                :aria-label="$t('efmv.item.quantity')"
                :title="$t('efmv.scenario.quantityRule')"
                data-testid="quantity"
              />
            </td>
            <!-- Software / a service of its own: what it is (empty: the placeholder) -->
            <td v-if="isStandalone(item)" class="cell-input" data-col="description">
              <v-text-field
                v-model="item.description"
                variant="plain"
                density="compact"
                hide-details
                maxlength="100"
                :placeholder="defaultName(item.kind!)"
                :aria-label="$t('efmv.item.description')"
                data-testid="description"
              >
                <template #prepend-inner>
                  <v-chip
                    size="x-small"
                    label
                    :color="KIND_LOOK[item.kind!].color"
                    variant="tonal"
                    :prepend-icon="KIND_LOOK[item.kind!].icon"
                    class="mr-1"
                    data-testid="kind-chip"
                  >
                    {{ $t(`efmv.kinds.${item.kind}Short`) }}
                  </v-chip>
                </template>
              </v-text-field>
              <div v-for="message in itemError(i)" :key="message" class="text-caption text-error">
                {{ message }}
              </div>
            </td>
            <td v-else :class="item.pending ? 'cell-input' : 'cell-text'" data-col="asset">
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
              <div v-else-if="isDeleted(item)" class="text-medium-emphasis text-caption">
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
                :model-value="unitShown(item, i)"
                inputmode="decimal"
                :placeholder="
                  detail(i)?.original_value ? toInputMoney(detail(i)!.original_value!, locale) : ''
                "
                variant="plain"
                density="compact"
                hide-details
                class="text-end-input"
                :class="{ 'net-shown': netShown(item, i) }"
                :rules="
                  isStandalone(item)
                    ? requiredValueRules
                    : isDeleted(item) || item.pending
                      ? []
                      : unitValueRules
                "
                :disabled="isDeleted(item) || !!item.pending"
                :aria-label="$t('efmv.item.unitValue')"
                :title="
                  netShown(item, i)
                    ? $t('efmv.service.netHint', {
                        value: `${symbol} ${toInputMoney(detail(i)!.net_unit_value!, locale)}`,
                      })
                    : $t('efmv.item.unitValueHint')
                "
                data-testid="unit-value"
                @update:model-value="item.unit_value = $event"
                @focus="editingUnit = item.key"
                @blur="onUnitBlur(item)"
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
                  isStandalone(item)
                    ? toInputMoney('0', locale)
                    : detail(i)?.curve_value
                      ? toInputMoney(detail(i)!.curve_value!, locale)
                      : ''
                "
                variant="plain"
                density="compact"
                hide-details
                class="text-end-input"
                :rules="isDeleted(item) || item.pending ? [] : efmvValueRules"
                :disabled="isDeleted(item) || !!item.pending || item.kind === 'sv'"
                :aria-label="$t('efmv.item.efmvValue')"
                :title="
                  item.kind === 'sv'
                    ? $t('efmv.service.efmvHint')
                    : item.kind === 'sw'
                      ? $t('efmv.software.efmvHint')
                      : $t('efmv.item.efmvValueHint', { term: scenario.term })
                "
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
          </tr>
          <!-- What is attached to it — software (SW), then service (SV): per unit, the asset's
               quantity; a service's eFMV is 0, software's is typed (empty: 0) -->
          <template v-for="key in ATTACHMENTS" :key="`${key}-${item.key}`">
            <tr
              v-if="item[key]"
              class="service-row"
              :class="{
                'row-off': detail(i)?.[key]?.too_high,
                'row-selected': selected === attachmentRowId(key, item.key),
              }"
              :aria-selected="selected === attachmentRowId(key, item.key)"
              :data-testid="`${key}-row`"
              @click="selected = attachmentRowId(key, item.key)"
              @contextmenu.prevent="openMenu($event, attachmentRowId(key, item.key))"
            >
              <!-- No number nor quantity: it follows its asset's -->
              <td class="row-number" />
              <td class="cell-text" />
              <td class="cell-input" :data-col="`${key}-name`">
                <v-text-field
                  v-model="item[key]!.name"
                  variant="plain"
                  density="compact"
                  hide-details
                  maxlength="100"
                  :placeholder="defaultName(ATTACHMENT_KIND[key])"
                  :aria-label="$t(`efmv.${key}.name`)"
                  :data-testid="`${key}-name`"
                >
                  <template #prepend-inner>
                    <v-chip
                      size="x-small"
                      label
                      :color="KIND_LOOK[ATTACHMENT_KIND[key]].color"
                      variant="tonal"
                      class="mr-1"
                    >
                      {{ $t(`efmv.kinds.${ATTACHMENT_KIND[key]}Short`) }}
                    </v-chip>
                  </template>
                </v-text-field>
                <div
                  v-for="message in [
                    ...(detail(i)?.[key]?.too_high && !attachmentErrors(i, key).length
                      ? [$t('efmv.service.tooHigh')]
                      : []),
                    ...attachmentErrors(i, key),
                  ]"
                  :key="message"
                  class="text-caption text-error px-3 pb-1"
                  :data-testid="`${key}-error`"
                >
                  {{ message }}
                </div>
              </td>
              <!-- Its value (money or "8%") and whether it is added to the asset or deducted -->
              <td class="cell-input money-cell" :data-col="`${key}-value`">
                <v-text-field
                  v-model="item[key]!.value"
                  inputmode="decimal"
                  variant="plain"
                  density="compact"
                  hide-details
                  class="text-end-input"
                  :rules="serviceValueRules"
                  :aria-label="$t(`efmv.${key}.value`)"
                  :title="$t('efmv.service.valueHint')"
                  :data-testid="`${key}-value`"
                  @blur="tidyAttachmentValue(item, key)"
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
                    :color="item[key]!.mode === 'deduct' ? 'warning' : 'primary'"
                    :prepend-icon="item[key]!.mode === 'deduct' ? 'mdi-minus' : 'mdi-plus'"
                    :title="$t('efmv.service.modeHint')"
                    :data-testid="`${key}-mode`"
                    @click="toggleMode(item, key)"
                  >
                    {{ $t(`efmv.service.${item[key]!.mode}`) }}
                  </v-chip>
                </div>
              </td>
              <!-- Software: its eFMV (empty: 0); services are not resold (nothing shown) -->
              <td v-if="key === 'software'" class="cell-input money-cell" data-col="software-efmv">
                <v-text-field
                  v-model="item.software!.efmv"
                  inputmode="decimal"
                  :placeholder="toInputMoney('0', locale)"
                  variant="plain"
                  density="compact"
                  hide-details
                  class="text-end-input"
                  :rules="efmvValueRules"
                  :aria-label="$t('efmv.item.efmvValue')"
                  :title="$t('efmv.software.efmvHint')"
                  data-testid="software-efmv"
                  @blur="tidySoftwareEfmv(item)"
                >
                  <template #prepend-inner
                    ><span class="symbol">{{ symbol }}</span></template
                  >
                </v-text-field>
                <div class="chip-line">
                  <v-chip
                    v-if="detail(i)?.software?.efmv_percent"
                    size="x-small"
                    variant="tonal"
                    label
                    class="cell-chip numeric"
                    :title="$t('efmv.item.efmvPercentHint')"
                  >
                    {{
                      $t('efmv.item.efmvPercent', {
                        percent: $n(Number(detail(i)!.software!.efmv_percent), 'percentValue'),
                      })
                    }}
                  </v-chip>
                </div>
              </td>
              <td v-else class="cell-text" :title="$t('efmv.service.efmvHint')" />
              <td class="money-cell text-no-wrap numeric font-weight-medium">
                <div v-if="detail(i)?.[key] && !detail(i)![key]!.too_high" class="money">
                  <span class="symbol font-weight-regular">{{ symbol }}</span>
                  <span :data-testid="`${key}-total`">{{
                    toInputMoney(detail(i)![key]!.line_total, locale)
                  }}</span>
                </div>
                <div v-else class="money justify-end">—</div>
                <div class="chip-line">
                  <v-chip
                    v-if="detail(i)?.[key]?.weight_percent"
                    size="x-small"
                    variant="tonal"
                    label
                    class="cell-chip numeric font-weight-regular"
                    :title="$t('efmv.item.weightHint')"
                    :data-testid="`${key}-weight`"
                  >
                    {{
                      $t('efmv.item.weightPercent', {
                        percent: $n(Number(detail(i)![key]!.weight_percent), 'percentValue'),
                      })
                    }}
                  </v-chip>
                </div>
              </td>
            </tr>
          </template>
        </template>
      </tbody>
    </v-table>

    <!-- The row's menu (right click) -->
    <v-menu
      v-model="menu.open"
      :target="[menu.x, menu.y]"
      location="bottom start"
      data-testid="row-menu"
    >
      <v-list density="compact" min-width="220" data-testid="row-menu-list">
        <v-list-item
          v-for="kind in ['hw', 'sw', 'sv'] as const"
          :key="kind"
          :prepend-icon="KIND_LOOK[kind].icon"
          :title="$t(`efmv.selection.add_${kind}`)"
          :data-testid="`menu-add-${kind}`"
          @click="addRow(kind)"
        />
        <v-divider class="my-1" />
        <v-list-item
          v-for="key in ATTACHMENTS"
          :key="key"
          prepend-icon="mdi-link-variant"
          :title="$t(`efmv.selection.attach_${key}`)"
          :disabled="!canAttach(key)"
          :data-testid="`menu-attach-${key}`"
          @click="attachToSelected(key)"
        />
        <v-divider class="my-1" />
        <v-list-item
          prepend-icon="mdi-delete-outline"
          :title="$t('efmv.selection.remove')"
          base-color="error"
          data-testid="menu-remove"
          @click="removeSelected"
        />
      </v-list>
    </v-menu>
  </div>
</template>

<style scoped>
/* The scenario's head: fields on the left, figures on the right, row by row */
.head-grid {
  display: grid;
  grid-template-columns: 1fr;
  gap: 8px 12px;
}
@media (min-width: 1280px) {
  .head-grid {
    grid-template-columns: 1fr 1fr;
    align-items: start;
  }
  /* The scope and the HW / SW / SV panel share their line: same top, same height */
  .head-scope,
  .head-shares {
    align-self: stretch;
  }
  .head-scope :deep(.v-input__control),
  .head-scope :deep(.v-field) {
    height: 100%;
  }
}
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
/* Service rows: a light tint, under their asset */
.sheet tbody tr.service-row > td:not(.row-number) {
  background: rgba(var(--v-theme-secondary), 0.04);
}
/* The selected row: tinted, a mark on its left */
.sheet tbody tr {
  cursor: default;
}
.sheet tbody tr.row-selected > td {
  background: rgba(var(--v-theme-primary), 0.1) !important;
}
.sheet tbody tr.row-selected > td:first-child {
  box-shadow: inset 3px 0 0 rgb(var(--v-theme-primary));
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
/* The asset's value without its deducted service (not the value typed) */
.net-shown :deep(input) {
  color: rgb(var(--v-theme-warning));
  font-weight: 600;
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
