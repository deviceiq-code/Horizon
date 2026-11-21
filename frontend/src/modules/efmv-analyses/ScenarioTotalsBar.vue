<script setup lang="ts">
/**
 * Figures of a scenario as computed by the API: LO and eFMV at the end of the lease (larger),
 * then the HW/SW/SV shares of the LO.
 */
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { formatMoney } from '@/utils/money'
import type { ScenarioTotals } from './api'

const props = defineProps<{ totals: ScenarioTotals | null; currency: string; loading?: boolean }>()
const { n, locale } = useI18n()

const percent = (value: string | null | undefined) =>
  value === null || value === undefined ? '—' : `${n(Number(value), 'percentValue')}%`

const figures = computed(() => [
  { key: 'lo', main: true, label: 'efmv.totals.lo', hint: 'efmv.totals.loHint',
    text: props.totals ? formatMoney(props.totals.lo, props.currency, locale.value) : '—' },
  { key: 'efmv', main: true, label: 'efmv.totals.efmv', hint: 'efmv.totals.efmvHint',
    text: percent(props.totals?.efmv_percent),
    detail: props.totals?.efmv_percent
      ? formatMoney(props.totals.efmv_total, props.currency, locale.value)
      : '' },
  { key: 'hw', main: false, label: 'efmv.totals.hw', hint: 'efmv.totals.hwHint',
    text: percent(props.totals?.hw_percent) },
  { key: 'sw', main: false, label: 'efmv.totals.sw', hint: 'efmv.totals.swHint',
    text: percent(props.totals?.sw_percent) },
  { key: 'sv', main: false, label: 'efmv.totals.sv', hint: 'efmv.totals.svHint',
    text: percent(props.totals?.sv_percent) },
]) // prettier-ignore
</script>

<template>
  <div class="totals" :class="{ 'opacity-60': loading }" data-testid="totals">
    <!-- The hint sits on a wrapper: on v-card, `title` would become its title -->
    <div
      v-for="figure in figures"
      :key="figure.key"
      class="figure"
      :class="{ main: figure.main }"
      :title="$t(figure.hint)"
      :data-testid="`total-${figure.key}`"
    >
      <v-card
        class="px-3 py-1 h-100"
        :color="figure.main ? 'primary' : undefined"
        :variant="figure.main ? 'tonal' : 'outlined'"
        flat
      >
        <div class="text-caption text-medium-emphasis text-no-wrap">{{ $t(figure.label) }}</div>
        <div
          class="font-weight-medium text-no-wrap"
          :class="figure.main ? 'text-h6' : 'text-subtitle-1'"
        >
          {{ figure.text }}
          <span
            v-if="'detail' in figure && figure.detail"
            class="text-body-2 text-medium-emphasis ml-1"
            data-testid="efmv-total"
          >
            · {{ figure.detail }}
          </span>
        </div>
      </v-card>
    </div>
  </div>
</template>

<style scoped>
.totals {
  display: grid;
  grid-template-columns: repeat(6, 1fr);
  gap: 8px;
}
.figure {
  grid-column: span 2;
  min-width: 0;
}
.figure.main {
  grid-column: span 3;
}
</style>
