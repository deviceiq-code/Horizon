<script setup lang="ts">
/**
 * The scenarios of an analysis, in its expanded row on the list: official name, assets, LO,
 * eFMV at EOL and the HW / SW / SV shares (a stacked bar). Loaded when the row is expanded;
 * every figure comes from the API.
 */
import { computed, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { formatMoney } from '@/utils/money'
import AssetCounts from './AssetCounts.vue'
import { getEfmvAnalysis, type EfmvAnalysis, type Scenario } from './api'
import { assetCounts } from './draft'

const props = defineProps<{ analysisId: number }>()
const emit = defineEmits<{ open: [] }>()
const { n, locale } = useI18n()

const analysis = ref<EfmvAnalysis | null>(null)
const loading = ref(true)
const failed = ref(false)

async function load() {
  loading.value = true
  failed.value = false
  try {
    analysis.value = await getEfmvAnalysis(props.analysisId)
  } catch {
    failed.value = true
  } finally {
    loading.value = false
  }
}
onMounted(load)

const SHARES = [
  { key: 'hw', color: 'primary' },
  { key: 'sw', color: 'info' },
  { key: 'sv', color: 'warning' },
] as const

const shareOf = (scenario: Scenario, key: (typeof SHARES)[number]['key']) => {
  const value = scenario.totals[`${key}_percent`]
  return value === null ? null : Number(value)
}

const currencyOf = (scenario: Scenario) => scenario.items.find((i) => i.currency)?.currency ?? 'BRL'

const money = (scenario: Scenario, value: string) =>
  formatMoney(value, currencyOf(scenario), locale.value)
const percent = (value: string | number | null) =>
  value === null ? '—' : `${n(Number(value), 'percentValue')}%`

const scenarios = computed(() => analysis.value?.scenarios ?? [])
</script>

<template>
  <div class="scenarios-panel" data-testid="analysis-scenarios">
    <v-skeleton-loader v-if="loading" type="table-row@2" />
    <v-alert v-else-if="failed" type="error" variant="tonal" density="compact">
      {{ $t('common.loadError') }}
      <template #append>
        <v-btn variant="text" size="small" @click="load">{{ $t('common.retry') }}</v-btn>
      </template>
    </v-alert>
    <v-table v-else density="compact" class="scenarios-table">
      <thead>
        <tr>
          <th>{{ $t('efmv.list.scenario') }}</th>
          <th class="text-end">{{ $t('efmv.scenario.assets') }}</th>
          <th class="text-end">{{ $t('efmv.totals.lo') }}</th>
          <th class="text-end">{{ $t('efmv.totals.efmv') }}</th>
          <th style="min-width: 260px">{{ $t('efmv.list.shares') }}</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="scenario in scenarios" :key="scenario.id" data-testid="analysis-scenario">
          <td class="font-weight-medium">
            <a href="#" class="text-primary" @click.prevent="emit('open')">{{ scenario.title }}</a>
            <div v-if="scenario.scope" class="text-caption text-medium-emphasis text-truncate">
              {{ scenario.scope }}
            </div>
          </td>
          <td class="text-end">
            <AssetCounts :counts="assetCounts(scenario.items)" />
          </td>
          <td class="text-end numeric text-no-wrap" data-testid="scenario-lo">
            {{ money(scenario, scenario.totals.lo) }}
          </td>
          <td class="text-end numeric text-no-wrap" data-testid="scenario-efmv">
            <span class="font-weight-medium">{{ percent(scenario.totals.efmv_percent) }}</span>
            <div v-if="scenario.totals.efmv_percent" class="text-caption text-medium-emphasis">
              {{ money(scenario, scenario.totals.efmv_total) }}
            </div>
          </td>
          <td data-testid="scenario-shares">
            <!-- One bar, a segment per share of the LO -->
            <div class="share-bar" :title="$t('efmv.list.sharesHint')">
              <div
                v-for="share in SHARES"
                v-show="(shareOf(scenario, share.key) ?? 0) > 0"
                :key="share.key"
                class="share-segment"
                :class="`bg-${share.color}`"
                :style="{ width: `${shareOf(scenario, share.key) ?? 0}%` }"
              />
            </div>
            <div class="d-flex ga-3 text-caption mt-1">
              <span
                v-for="share in SHARES"
                :key="share.key"
                class="d-flex align-center ga-1 text-no-wrap"
                :data-testid="`scenario-${share.key}`"
              >
                <span class="dot" :class="`bg-${share.color}`" />
                {{ $t(`efmv.totals.${share.key}`) }}
                <span class="numeric">{{ percent(shareOf(scenario, share.key)) }}</span>
              </span>
            </div>
          </td>
        </tr>
      </tbody>
    </v-table>
  </div>
</template>

<style scoped>
.scenarios-panel {
  padding: 8px 16px 12px 56px;
}
.scenarios-table {
  background: transparent;
}
.scenarios-table :deep(th) {
  font-size: 0.75rem;
  color: rgba(var(--v-theme-on-surface), var(--v-medium-emphasis-opacity));
}
.numeric {
  font-variant-numeric: tabular-nums;
}
.share-bar {
  display: flex;
  height: 8px;
  border-radius: 4px;
  overflow: hidden;
  background: rgba(var(--v-theme-on-surface), 0.08);
}
.share-segment {
  height: 100%;
}
.dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  display: inline-block;
}
</style>
