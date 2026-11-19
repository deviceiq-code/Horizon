<script setup lang="ts">
/**
 * The value at each term of the sub-vertical (12, 24, 36… months), entered as a fixed value
 * or as a % of the original value. The other representation and the warnings come from the
 * API preview (`resolved`): this component never computes prices.
 */
import { useI18n } from 'vue-i18n'
import { formatMoney, parseMoney } from '@/utils/money'
import type { AnchorMode, PreviewResult } from './api'

export interface TermEntry {
  mode: AnchorMode
  /** As typed, in the UI language */
  text: string
}

const entries = defineModel<Record<number, TermEntry>>({ required: true })
defineProps<{
  terms: number[]
  currency: string
  /** Resolved values from the API preview, if available */
  resolved: PreviewResult | null
  errors?: Record<number, string[]>
}>()

const { t, locale, n } = useI18n()

function rulesFor(mode: AnchorMode) {
  return [
    (v: string) => !!v?.trim() || t('validation.required'),
    (v: string) =>
      parseMoney(v, locale.value, mode === 'percent' ? 4 : 2) !== null ||
      (mode === 'percent' ? t('averagePrices.invalidPercent') : t('averagePrices.invalidValue')),
  ]
}

function resolvedFor(resolved: PreviewResult | null, term: number) {
  return resolved?.points.find((p) => p.term_months === term)
}
</script>

<template>
  <v-table density="comfortable" class="term-points">
    <thead>
      <tr>
        <th style="width: 120px">{{ $t('averagePrices.fields.term') }}</th>
        <th style="width: 150px">{{ $t('averagePrices.fields.enteredAs') }}</th>
        <th>{{ $t('averagePrices.fields.amount') }}</th>
        <th class="text-end" style="width: 220px">{{ $t('averagePrices.fields.result') }}</th>
      </tr>
    </thead>
    <tbody>
      <tr v-for="term in terms" :key="term" :data-testid="`term-${term}`">
        <td class="font-weight-medium text-no-wrap">{{ $t('verticals.months', term) }}</td>
        <td>
          <v-btn-toggle
            v-model="entries[term]!.mode"
            mandatory
            density="compact"
            variant="outlined"
            color="primary"
            divided
            data-testid="term-mode"
          >
            <v-btn value="percent" size="small" data-testid="mode-percent">%</v-btn>
            <v-btn value="value" size="small" data-testid="mode-value">{{ currency }}</v-btn>
          </v-btn-toggle>
        </td>
        <td class="py-2">
          <v-text-field
            v-model="entries[term]!.text"
            :prefix="entries[term]!.mode === 'value' ? currency : undefined"
            :suffix="entries[term]!.mode === 'percent' ? '%' : undefined"
            inputmode="decimal"
            density="compact"
            hide-details="auto"
            :rules="rulesFor(entries[term]!.mode)"
            :error-messages="errors?.[term]"
            data-testid="term-amount"
          />
        </td>
        <td class="text-end text-no-wrap" data-testid="term-result">
          <template v-if="resolvedFor(resolved, term)">
            <v-icon
              v-if="resolved?.increasing_terms.includes(term)"
              icon="mdi-alert-outline"
              color="warning"
              size="small"
              class="mr-1"
              :title="$t('averagePrices.increasingTermHint')"
            />
            <span class="font-weight-medium">
              {{ formatMoney(resolvedFor(resolved, term)!.value, currency, locale) }}
            </span>
            <span class="text-medium-emphasis">
              · {{ n(Number(resolvedFor(resolved, term)!.percent), 'percentValue') }}%
            </span>
          </template>
          <span v-else class="text-medium-emphasis">—</span>
        </td>
      </tr>
    </tbody>
  </v-table>
</template>
