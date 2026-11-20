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
import { previewScenario, type ScenarioItem } from './api'
import {
  MAX_TERM,
  newKey,
  parseTerm,
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

const { t, locale } = useI18n()
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
  const input = scenarioInput(scenario.value)
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
    available: false,
    average_price: null,
    line_total: null,
    out_of_curve: false,
  }
}

const watched = computed(() =>
  JSON.stringify([
    scenario.value.term,
    scenario.value.items.map((i) => [i.average_price, i.quantity]),
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

function addAsset(id: number) {
  scenario.value.items.push({ key: newKey(), average_price: id, quantity: 1 })
  // Placeholder (loading) until the API answers
  scenario.value.preview?.items.push({ ...deletedItem(1), available: true })
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
  return [...(errors?.average_price ?? []), ...(errors?.quantity ?? [])]
}
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
        <AveragePricePicker
          :label="$t('efmv.scenario.addAsset')"
          :exclude="chosen"
          prepend-inner-icon="mdi-plus"
          density="compact"
          hide-details
          class="add-asset"
          data-testid="add-asset"
          @pick="addAsset"
        />
      </div>
    </div>

    <v-table density="comfortable" fixed-header class="assets" data-testid="assets">
      <thead>
        <tr>
          <th>{{ $t('efmv.item.asset') }}</th>
          <th class="text-end">{{ $t('efmv.item.unitValue') }}</th>
          <th style="width: 120px">{{ $t('efmv.item.quantity') }}</th>
          <th class="text-end">{{ $t('efmv.item.total') }}</th>
          <th style="width: 48px"></th>
        </tr>
      </thead>
      <tbody>
        <tr v-if="!scenario.items.length">
          <td colspan="5" class="text-medium-emphasis text-center py-6">
            {{ $t('efmv.scenario.noAssets') }}
          </td>
        </tr>
        <tr v-for="(item, i) in scenario.items" :key="item.key" data-testid="asset-row">
          <td class="py-2">
            <div v-if="detail(i)?.asset_class" class="d-flex align-center ga-3">
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
          <td class="text-end text-no-wrap">
            {{
              detail(i)?.original_value
                ? formatMoney(detail(i)!.original_value!, detail(i)!.currency ?? 'BRL', locale)
                : '—'
            }}
          </td>
          <td>
            <v-text-field
              v-model.number="item.quantity"
              type="number"
              min="1"
              density="compact"
              hide-details="auto"
              :rules="quantityRules"
              :disabled="item.average_price === null"
              :aria-label="$t('efmv.item.quantity')"
              data-testid="quantity"
            />
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
.add-asset {
  flex: 0 1 460px;
  min-width: 260px;
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
