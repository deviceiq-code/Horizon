<script setup lang="ts">
/** Figures of a scenario as computed by the API: LO, eFMV at the end of the lease, HW/SW/SV. */
import { useI18n } from 'vue-i18n'
import { formatMoney } from '@/utils/money'
import type { ScenarioTotals } from './api'

const props = defineProps<{ totals: ScenarioTotals | null; currency: string; loading?: boolean }>()
const { n, locale } = useI18n()

const percent = (value: string | null | undefined) =>
  value === null || value === undefined ? '—' : `${n(Number(value), 'percentValue')}%`

const figures = () => [
  { key: 'lo', label: 'efmv.totals.lo', hint: 'efmv.totals.loHint',
    text: props.totals ? formatMoney(props.totals.lo, props.currency, locale.value) : '—' },
  { key: 'efmv', label: 'efmv.totals.efmv', hint: 'efmv.totals.efmvHint',
    text: percent(props.totals?.efmv_percent) },
  { key: 'hw', label: 'efmv.totals.hw', hint: 'efmv.totals.hwHint',
    text: percent(props.totals?.hw_percent) },
  { key: 'sw', label: 'efmv.totals.sw', hint: 'efmv.totals.swHint',
    text: percent(props.totals?.sw_percent) },
  { key: 'sv', label: 'efmv.totals.sv', hint: 'efmv.totals.svHint',
    text: percent(props.totals?.sv_percent) },
] // prettier-ignore
</script>

<template>
  <div class="totals d-flex flex-wrap ga-2" :class="{ 'opacity-60': loading }">
    <v-sheet
      v-for="figure in figures()"
      :key="figure.key"
      class="figure px-3 py-2"
      :class="{ main: figure.key === 'lo' || figure.key === 'efmv' }"
      rounded
      border
      :title="$t(figure.hint)"
      :data-testid="`total-${figure.key}`"
    >
      <div class="text-caption text-medium-emphasis text-no-wrap">{{ $t(figure.label) }}</div>
      <div class="text-subtitle-1 font-weight-medium text-no-wrap">{{ figure.text }}</div>
    </v-sheet>
  </div>
</template>

<style scoped>
.figure {
  min-width: 96px;
  flex: 1 1 96px;
}
.figure.main {
  flex: 2 1 180px;
}
</style>
