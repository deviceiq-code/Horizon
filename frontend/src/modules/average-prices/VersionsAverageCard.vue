<script setup lang="ts">
/** Average of the versions of an average price (computed by the API): original value and each term. */
import { useI18n } from 'vue-i18n'
import { formatMoney } from '@/utils/money'
import type { VersionsAverage } from './api'

const props = defineProps<{ average: VersionsAverage; currency: string }>()

const { locale, n } = useI18n()

const money = (value: string) => formatMoney(value, props.currency, locale.value)
const percent = (value: string) => `${n(Number(value), 'percentValue')}%`
</script>

<template>
  <v-card variant="tonal" color="primary" data-testid="history-average">
    <v-card-item>
      <v-card-title class="text-subtitle-1">
        {{ $t('averagePrices.average.title', { n: average.count }) }}
      </v-card-title>
      <v-card-subtitle>
        {{ $t('averagePrices.fields.originalValue') }}:
        <strong>{{ money(average.original_value) }}</strong>
      </v-card-subtitle>
    </v-card-item>
    <v-card-text class="pt-0">
      <div class="d-flex flex-wrap ga-2">
        <v-chip
          v-for="point in average.points"
          :key="point.term_months"
          size="small"
          variant="flat"
          color="surface"
          :title="
            point.count < average.count
              ? $t('averagePrices.average.partial', { count: point.count, total: average.count })
              : undefined
          "
          data-testid="average-point"
        >
          <span class="text-medium-emphasis mr-1">{{
            $t('verticals.months', point.term_months)
          }}</span>
          <span class="font-weight-medium">{{ money(point.value) }}</span>
          <span class="ml-1">· {{ percent(point.percent) }}</span>
          <span v-if="point.count < average.count" class="ml-1">*</span>
        </v-chip>
      </div>
    </v-card-text>
  </v-card>
</template>
