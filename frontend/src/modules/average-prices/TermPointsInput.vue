<script setup lang="ts">
/**
 * The value at each term of the sub-vertical (12, 24, 36… months), as in the eFMV analyses:
 * one field per term taking money in the currency or a % of the original value ("70%"); once
 * the field is left, a % becomes its value. Below it, what the value is of the original value
 * ("% Value (70.00%)"). Values and warnings come from the API preview (`resolved`): this
 * component never computes prices.
 */
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { currencySymbol, toInputMoney } from '@/utils/money'
import type { PreviewResult } from './api'
import { parseTermInput } from './termInput'

export interface TermEntry {
  /** As typed, in the UI language: a value or a percentage ("70%") */
  text: string
}

const entries = defineModel<Record<number, TermEntry>>({ required: true })
const props = defineProps<{
  terms: number[]
  currency: string
  /** Resolved values from the API preview, if available */
  resolved: PreviewResult | null
  errors?: Record<number, string[]>
}>()

const { t, locale, n } = useI18n()
const symbol = computed(() => currencySymbol(props.currency, locale.value))

const rules = [
  (v: string) => !!v?.trim() || t('validation.required'),
  (v: string) => parseTermInput(v, locale.value) !== null || t('averagePrices.invalidTermValue'),
]

function resolvedFor(term: number) {
  return props.resolved?.points.find((p) => p.term_months === term)
}

// A % typed becomes its value when the field is left — as soon as the preview has it
const pending = ref<Record<number, string>>({})

function onBlur(term: number) {
  const text = entries.value[term]?.text ?? ''
  if (parseTermInput(text, locale.value)?.mode === 'percent') pending.value[term] = text
  convertPending()
}

function convertPending() {
  for (const [key, typed] of Object.entries(pending.value)) {
    const term = Number(key)
    const entry = entries.value[term]
    const parsed = parseTermInput(typed, locale.value)
    // Typed again meanwhile: nothing to convert
    if (!entry || entry.text !== typed || parsed?.mode !== 'percent') {
      delete pending.value[term]
      continue
    }
    const point = resolvedFor(term)
    // Only a preview of this very percentage (not one still on its way for an older text)
    if (!point || Math.abs(Number(point.percent) - Number(parsed.amount)) >= 0.01) continue
    entry.text = toInputMoney(point.value, locale.value)
    delete pending.value[term]
  }
}

watch(() => props.resolved, convertPending)
</script>

<template>
  <v-table density="comfortable" class="term-points">
    <thead>
      <tr>
        <th style="width: 140px">{{ $t('averagePrices.fields.term') }}</th>
        <th class="text-end">{{ $t('averagePrices.fields.amount') }}</th>
      </tr>
    </thead>
    <tbody>
      <tr v-for="term in terms" :key="term" :data-testid="`term-${term}`">
        <td class="font-weight-medium text-no-wrap">{{ $t('verticals.months', term) }}</td>
        <td class="py-2">
          <div class="d-flex align-center ga-2">
            <v-icon
              v-if="resolved?.increasing_terms.includes(term)"
              icon="mdi-alert-outline"
              color="warning"
              size="small"
              :title="$t('averagePrices.increasingTermHint')"
              data-testid="term-increasing"
            />
            <v-text-field
              v-model="entries[term]!.text"
              inputmode="decimal"
              :placeholder="$t('averagePrices.termPlaceholder')"
              density="compact"
              hide-details="auto"
              class="term-amount"
              :rules="rules"
              :error-messages="errors?.[term]"
              data-testid="term-amount"
              @blur="onBlur(term)"
            >
              <!-- Always shown (a prefix only shows once there is a value) -->
              <template #prepend-inner
                ><span class="symbol">{{ symbol }}</span></template
              >
            </v-text-field>
          </div>
          <!-- What the value is of the original value: the eFMV cells' chip -->
          <div class="chip-line">
            <v-chip
              v-if="resolvedFor(term)"
              size="x-small"
              variant="tonal"
              label
              class="numeric"
              :title="$t('averagePrices.termPercentHint')"
              data-testid="term-percent"
            >
              {{
                $t('efmv.item.efmvPercent', {
                  percent: n(Number(resolvedFor(term)!.percent), 'percentValue'),
                })
              }}
            </v-chip>
          </div>
        </td>
      </tr>
    </tbody>
  </v-table>
</template>

<style scoped>
.term-amount {
  max-width: 320px;
  margin-left: auto;
}
.term-amount :deep(input) {
  text-align: end;
  font-variant-numeric: tabular-nums;
}
.symbol {
  color: rgba(var(--v-theme-on-surface), var(--v-medium-emphasis-opacity));
  white-space: nowrap;
  margin-right: 4px;
}
.chip-line {
  display: flex;
  justify-content: flex-end;
  min-height: 20px;
  margin-top: 2px;
}
.numeric {
  font-variant-numeric: tabular-nums;
}
</style>
