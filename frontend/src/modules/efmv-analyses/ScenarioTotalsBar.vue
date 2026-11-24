<script setup lang="ts">
/**
 * Figures of a scenario as computed by the API, in two parts (the scenario's head lines them
 * up with its fields): `main` — LO and eFMV at the end of the lease, larger — and `shares` —
 * the LO's mix: one bar with a segment per share (HW / SW / SV, the same colors as the list's
 * expanded rows) and below it each share with its icon, percentage and value.
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

/** A share of the LO: its percentage, its value and its part of the bar */
const SHARE_LOOK = {
  hw: { color: 'primary', icon: 'mdi-desktop-tower-monitor' },
  sw: { color: 'info', icon: 'mdi-application-brackets-outline' },
  sv: { color: 'warning', icon: 'mdi-wrench-outline' },
} as const
const share = (key: 'hw' | 'sw' | 'sv') => {
  const value = props.totals?.[`${key}_percent`]
  return {
    key,
    main: false,
    label: `efmv.totals.${key}`,
    hint: `efmv.totals.${key}Hint`,
    text: percent(value),
    detail: value ? money(props.totals![`${key}_total`]) : '',
    width: value ? Math.max(0, Math.min(100, Number(value))) : 0,
    ...SHARE_LOOK[key],
  }
}
const shares = computed(() => [share('hw'), share('sw'), share('sv')])
const hasMix = computed(() => shares.value.some((s) => s.width > 0))

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
  <!-- The LO's mix: one bar, then each share -->
  <v-card
    v-if="part === 'shares'"
    variant="flat"
    flat
    class="mix px-3 py-2 h-100 d-flex flex-column justify-center"
    :class="{ 'opacity-60': loading }"
    data-testid="totals-shares"
  >
    <div class="mix-bar" :class="{ 'mix-bar--empty': !hasMix }" data-testid="mix-bar">
      <div
        v-for="item in shares"
        v-show="item.width > 0"
        :key="item.key"
        class="mix-segment"
        :class="`bg-${item.color}`"
        :style="{ width: `${item.width}%` }"
        :title="`${$t(item.label)} · ${item.text}`"
      />
    </div>
    <div class="mix-items">
      <div
        v-for="item in shares"
        :key="item.key"
        class="mix-item"
        :title="$t(item.hint)"
        :data-testid="`total-${item.key}`"
      >
        <v-avatar :color="item.color" variant="tonal" size="28" rounded="lg">
          <v-icon :icon="item.icon" size="16" />
        </v-avatar>
        <div class="min-w-0">
          <div class="d-flex align-baseline ga-1">
            <span class="text-caption text-medium-emphasis">{{ $t(item.label) }}</span>
            <span class="text-subtitle-2 font-weight-bold numeric">{{ item.text }}</span>
          </div>
          <div
            class="text-caption text-medium-emphasis text-truncate numeric"
            :title="item.detail"
            :data-testid="`${item.key}-total`"
          >
            {{ item.detail || '\u00a0' }}
          </div>
        </div>
      </div>
    </div>
  </v-card>
  <div
    v-else
    class="totals"
    :class="[`totals--${part}`, { 'opacity-60': loading }]"
    data-testid="totals"
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
/* Grey panel without a border */
.mix {
  background: rgba(var(--v-theme-on-surface), 0.05) !important;
  border: none !important;
}
.mix-bar {
  display: flex;
  height: 8px;
  border-radius: 4px;
  overflow: hidden;
  gap: 2px;
  margin-bottom: 8px;
}
.mix-bar--empty {
  background: rgba(var(--v-theme-on-surface), 0.12);
}
.mix-segment {
  transition: width 0.3s ease;
}
.mix-items {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 8px;
}
.mix-item {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
}
.min-w-0 {
  min-width: 0;
}
</style>
