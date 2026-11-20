<script setup lang="ts">
/**
 * One scenario of an analysis (a tab): name, term, scope and its figures on top; below, the
 * grid of its assets (current average prices with quantities), which fills the rest of the
 * page — only the assets scroll. Every change asks the API for the scenario's figures
 * (`preview`); nothing is computed here. Assets whose curve stops before the term are flagged
 * (saving refuses them).
 */
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useValidationRules } from '@/composables/useValidationRules'
import { formatMoney } from '@/utils/money'
import AveragePricePicker from './AveragePricePicker.vue'
import ScenarioTotalsBar from './ScenarioTotalsBar.vue'
import { previewScenario, type PricePosition, type ScenarioItem } from './api'
import {
  MAX_TERM,
  newKey,
  parseTerm,
  parseUnitValue,
  scenarioInput,
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
    const preview = await previewScenario({ term_months: term, items: input.items })
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
    scenario.value.items.map((i) => [i.average_price, i.quantity, i.unit_value]),
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
    pending: true,
  })
  scenario.value.preview?.items.push({ ...deletedItem(1), available: true })
}

function chooseAsset(index: number, id: number) {
  const item = scenario.value.items[index]!
  item.average_price = id
  item.pending = false
  // The value is typed by the analyst (Average Prices only positions it); the details come
  // with the next preview
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
  ]
}

const unitValueRules = [
  (v: string) => !!v?.trim() || t('validation.required'),
  (v: string) => parseUnitValue(v ?? '', locale.value) !== null || t('efmv.item.unitValueRule'),
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
    <v-table density="comfortable" fixed-header class="assets" data-testid="assets">
      <thead>
        <tr>
          <th style="width: 110px">{{ $t('efmv.item.quantity') }}</th>
          <th>{{ $t('efmv.item.asset') }}</th>
          <th style="width: 190px">{{ $t('efmv.item.unitValue') }}</th>
          <th>{{ $t('efmv.item.historical') }}</th>
          <th class="text-end">{{ $t('efmv.item.total') }}</th>
          <th style="width: 48px"></th>
        </tr>
      </thead>
      <tbody>
        <tr v-if="!scenario.items.length">
          <td colspan="6" class="text-medium-emphasis text-center py-6">
            {{ $t('efmv.scenario.noAssets') }}
          </td>
        </tr>
        <tr v-for="(item, i) in scenario.items" :key="item.key" data-testid="asset-row">
          <td>
            <v-text-field
              v-model.number="item.quantity"
              type="number"
              min="1"
              density="compact"
              hide-details="auto"
              :rules="item.average_price === null ? [] : quantityRules"
              :disabled="item.average_price === null"
              :aria-label="$t('efmv.item.quantity')"
              data-testid="quantity"
            />
          </td>
          <td class="py-2">
            <AveragePricePicker
              v-if="item.pending"
              :label="$t('efmv.scenario.chooseAsset')"
              :exclude="chosen"
              prepend-inner-icon="mdi-magnify"
              density="compact"
              hide-details
              autofocus
              data-testid="add-asset"
              @pick="chooseAsset(i, $event)"
            />
            <div v-else-if="detail(i)?.asset_class" class="d-flex align-center ga-3">
              <v-avatar color="primary" variant="tonal" size="32" rounded>
                <v-icon :icon="detail(i)!.asset_class!.icon" size="18" />
              </v-avatar>
              <div>
                <div class="font-weight-medium">
                  {{ detail(i)!.manufacturer }} {{ detail(i)!.model }}
                </div>
                <div class="text-caption text-medium-emphasis">
                  {{ detail(i)!.asset_class!.name }} ·
                  {{
                    $t('efmv.item.curveUpTo', { months: Math.max(...(detail(i)!.terms ?? [0])) })
                  }}
                </div>
              </div>
            </div>
            <div v-else-if="item.average_price === null" class="text-medium-emphasis">
              <v-icon icon="mdi-alert-outline" color="warning" size="small" class="mr-1" />
              {{ $t('efmv.item.deleted') }}
            </div>
            <v-progress-circular v-else indeterminate size="18" width="2" />
            <div
              v-if="detail(i)?.out_of_curve && !itemError(i).length"
              class="text-caption text-error mt-1"
              data-testid="out-of-curve"
            >
              <v-icon icon="mdi-alert-circle-outline" size="x-small" />
              {{ $t('efmv.item.outOfCurve', { term: scenario.term }) }}
            </div>
            <div
              v-for="message in itemError(i)"
              :key="message"
              class="text-caption text-error mt-1"
            >
              {{ message }}
            </div>
          </td>
          <td>
            <v-text-field
              v-model="item.unit_value"
              inputmode="decimal"
              :prefix="currency === 'BRL' ? 'R$' : currency"
              density="compact"
              hide-details="auto"
              :rules="item.average_price === null ? [] : unitValueRules"
              :disabled="item.average_price === null"
              :aria-label="$t('efmv.item.unitValue')"
              data-testid="unit-value"
            />
          </td>
          <td class="py-2">
            <template v-if="detail(i)?.original_value">
              <div class="text-no-wrap">
                {{ formatMoney(detail(i)!.original_value!, detail(i)!.currency ?? 'BRL', locale) }}
              </div>
              <div class="d-flex flex-wrap align-center ga-1 mt-1">
                <v-chip
                  v-if="detail(i)!.position"
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
                <v-chip
                  v-if="detail(i)!.expired"
                  color="warning"
                  prepend-icon="mdi-calendar-alert"
                  size="small"
                  variant="tonal"
                  label
                  :title="
                    $t('efmv.item.expiredHint', {
                      date: shortDate(detail(i)!.priced_on!),
                      until: shortDate(detail(i)!.valid_until!),
                    })
                  "
                  data-testid="expired"
                >
                  {{ $t('efmv.item.expired') }}
                </v-chip>
                <span v-else-if="detail(i)!.priced_on" class="text-caption text-medium-emphasis">
                  {{ $t('efmv.item.pricedOn', { date: shortDate(detail(i)!.priced_on!) }) }}
                </span>
              </div>
            </template>
            <span v-else>—</span>
          </td>
          <td class="text-end text-no-wrap" :class="{ 'text-disabled': detail(i)?.out_of_curve }">
            {{
              detail(i)?.line_total ? formatMoney(detail(i)!.line_total!, currency, locale) : '—'
            }}
          </td>
          <td>
            <v-btn
              icon="mdi-close"
              variant="text"
              size="small"
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
.assets :deep(td),
.assets :deep(th) {
  vertical-align: middle;
}
.assets {
  border-top: thin solid rgba(var(--v-border-color), var(--v-border-opacity));
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
