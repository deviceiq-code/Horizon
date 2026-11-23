<script setup lang="ts">
/**
 * Figures of a scenario as computed by the API, in two parts (the scenario's head lines them
 * up with its fields): `main` — LO and eFMV at the end of the lease, larger — and `shares` —
 * the HW / SW / SV shares of the LO, each as a percentage and its value.
 */
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { useNumberFormat } from '@/composables/useNumberFormat'
import { formatMoney } from '@/utils/money'
import type { ScenarioTotals } from './api'

const props = withDefaults(
  defineProps<{
    totals: ScenarioTotals | null
    currency: string
    loading?: boolean
    part?: 'main' | 'shares'
  }>(),
  { loading: false, part: 'main' },
)
const { locale } = useI18n()
const { n } = useNumberFormat()

const percent = (value: string | null | undefined) =>
  value === null || value === undefined ? '—' : `${n(Number(value), 'percentValue')}%`
const money = (value: string | undefined) =>
  value === undefined ? '' : formatMoney(value, props.currency, locale.value)

/** A share of the LO: its percentage and, beside it, its value */
const share = (key: 'hw' | 'sw' | 'sv') => ({
  key,
  main: false,
  label: `efmv.totals.${key}`,
  hint: `efmv.totals.${key}Hint`,
  text: percent(props.totals?.[`${key}_percent`]),
  detail: props.totals?.[`${key}_percent`] ? money(props.totals[`${key}_total`]) : '',
})

const figures = computed(() =>
  props.part === 'shares'
    ? [share('hw'), share('sw'), share('sv')]
    : [
        { key: 'lo', main: true, label: 'efmv.totals.lo', hint: 'efmv.totals.loHint',
          text: props.totals ? money(props.totals.lo) : '—', detail: '' },
        { key: 'efmv', main: true, label: 'efmv.totals.efmv', hint: 'efmv.totals.efmvHint',
          text: percent(props.totals?.efmv_percent),
          detail: props.totals?.efmv_percent ? money(props.totals.efmv_total) : '' },
      ],
) // prettier-ignore
</script>

<template>
  <div
    class="totals"
    :class="[`totals--${part}`, { 'opacity-60': loading }]"
    :data-testid="part === 'main' ? 'totals' : 'totals-shares'"
  >
    <!-- The hint sits on a wrapper: on v-card, `title` would become its title -->
    <div
      v-for="figure in figures"
      :key="figure.key"
      class="figure"
      :title="$t(figure.hint)"
      :data-testid="`total-${figure.key}`"
    >
      <v-card
        class="px-3 py-1 h-100 d-flex flex-column justify-center"
        :color="figure.main ? 'primary' : undefined"
        :variant="figure.main ? 'tonal' : 'outlined'"
        flat
      >
        <div class="text-caption text-medium-emphasis text-no-wrap">{{ $t(figure.label) }}</div>
        <div
          class="font-weight-medium text-no-wrap text-truncate"
          :class="figure.main ? 'text-h6' : 'text-subtitle-1'"
        >
          {{ figure.text }}
          <span
            v-if="figure.detail && figure.main"
            class="text-body-2 text-medium-emphasis ml-1"
            data-testid="efmv-total"
          >
            · {{ figure.detail }}
          </span>
        </div>
        <!-- A share's value: on its own line (narrower cards) -->
        <div
          v-if="figure.detail && !figure.main"
          class="text-body-2 text-medium-emphasis text-no-wrap text-truncate numeric"
          :title="figure.detail"
          :data-testid="`${figure.key}-total`"
        >
          {{ figure.detail }}
        </div>
      </v-card>
    </div>
  </div>
</template>

<style scoped>
.totals {
  display: grid;
  gap: 8px;
  height: 100%;
}
.totals--main {
  grid-template-columns: repeat(2, 1fr);
}
.totals--shares {
  grid-template-columns: repeat(3, 1fr);
}
.figure {
  min-width: 0;
}
.numeric {
  font-variant-numeric: tabular-nums;
}
</style>
