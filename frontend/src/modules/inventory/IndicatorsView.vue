<script setup lang="ts">
/**
 * The inventory's indicators (spec §10), for a period, a warehouse and/or a customer: number
 * tiles and horizontal bars drawn with Vuetify (no chart library — decision). Every figure
 * comes from the API (inventory/indicators.py).
 */
import { computed, onMounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { listWarehouses, type Warehouse } from '@/modules/warehouses/api'
import { formatMoney } from '@/utils/money'
import CustomerSelect from './CustomerSelect.vue'
import { getIndicators, type Indicators, type RatioRow } from './api'

const { t, locale } = useI18n()

const today = new Date()
const iso = (date: Date) => date.toISOString().slice(0, 10)
const from = ref(iso(new Date(today.getFullYear(), today.getMonth() - 2, 1)))
const to = ref(iso(today))
const warehouses = ref<Warehouse[]>([])
const warehouse = ref<number | null>(null)
const customer = ref<number | null>(null)
const data = ref<Indicators | null>(null)
const loading = ref(false)
const failed = ref(false)

async function load() {
  loading.value = true
  failed.value = false
  try {
    data.value = await getIndicators({
      from: from.value,
      to: to.value,
      warehouse: warehouse.value,
      customer: customer.value,
    })
  } catch {
    failed.value = true
  } finally {
    loading.value = false
  }
}
onMounted(async () => {
  try {
    warehouses.value = (await listWarehouses({ page: 1, pageSize: 200, ordering: 'name' })).results
  } catch {
    // The filter just lists no warehouses
  }
  await load()
})
watch([from, to, warehouse, customer], load)

const warehouseOptions = computed(() => [
  { value: null, title: t('common.filters.all') },
  ...warehouses.value.map((w) => ({ value: w.id, title: `${w.code} · ${w.name}` })),
])

const pct = (value: string | null | undefined) =>
  value === null || value === undefined
    ? '—'
    : `${Number(value).toLocaleString(locale.value, { maximumFractionDigits: 1 })}%`
const days = (value: string | null) =>
  value === null
    ? '—'
    : t('inventory.indicators.days', { n: Number(value).toLocaleString(locale.value) })
const money = (value: string) => formatMoney(value, 'BRL', locale.value)
const share = (row: RatioRow) => (row.percent === null ? 0 : Math.min(100, Number(row.percent)))

const tiles = computed(() => {
  const v = data.value
  if (!v) return []
  return [
    {
      key: 'leadTime',
      icon: 'mdi-timer-outline',
      value: days(v.lead_time.average_days),
      hint: t('inventory.indicators.units', { n: v.lead_time.units }),
    },
    {
      key: 'accuracy',
      icon: 'mdi-target',
      value: pct(v.location_accuracy.percent),
      hint: t('inventory.indicators.counts', { n: v.location_accuracy.counts.length }),
    },
    {
      key: 'withoutSerial',
      icon: 'mdi-barcode-off',
      value: pct(v.without_serial.percent),
      hint: '',
    },
    {
      key: 'blocksReleased',
      icon: 'mdi-lock-open-check-outline',
      value: pct(v.blocks_released.percent),
      hint: `${v.blocks_released.released} / ${v.blocks_released.closed}`,
    },
    {
      key: 'disputesUpheld',
      icon: 'mdi-gavel',
      value: pct(v.disputes_upheld.percent),
      hint: `${v.disputes_upheld.upheld} / ${v.disputes_upheld.decided}`,
    },
    { key: 'scrapRate', icon: 'mdi-delete-variant', value: pct(v.scrap_rate.percent), hint: '' },
  ]
})

const BAND_COLORS = ['success', 'info', 'warning', 'error']
const GRADE_LEVELS = ['A', 'B', 'C', 'D']
const GRADE_COLORS: Record<string, string> = { A: 'success', B: 'info', C: 'warning', D: 'error' }
</script>

<template>
  <v-container fluid class="module-page">
    <h1 class="mb-1">{{ $t('inventory.indicators.title') }}</h1>
    <p class="text-medium-emphasis mb-4">{{ $t('inventory.indicators.subtitle') }}</p>

    <v-row dense class="mb-2">
      <v-col cols="6" md="2">
        <v-text-field
          v-model="from"
          type="date"
          :label="$t('inventory.indicators.from')"
          density="compact"
          hide-details
        />
      </v-col>
      <v-col cols="6" md="2">
        <v-text-field
          v-model="to"
          type="date"
          :label="$t('inventory.indicators.to')"
          density="compact"
          hide-details
        />
      </v-col>
      <v-col cols="12" md="3">
        <v-select
          v-model="warehouse"
          :items="warehouseOptions"
          :label="$t('inventory.fields.warehouse')"
          density="compact"
          hide-details
        />
      </v-col>
      <v-col cols="12" md="3">
        <CustomerSelect
          v-model="customer"
          :label="$t('inventory.appointments.customer')"
          density="compact"
          hide-details
        />
      </v-col>
    </v-row>

    <v-progress-linear v-if="loading" indeterminate class="mb-2" />
    <v-alert v-if="failed" type="error" variant="tonal">{{ $t('common.loadError') }}</v-alert>

    <template v-if="data">
      <!-- Tiles -->
      <v-row dense class="mb-2">
        <v-col v-for="tile in tiles" :key="tile.key" cols="6" md="4" lg="2">
          <v-card class="pa-4 h-100" :data-testid="`tile-${tile.key}`">
            <div class="d-flex align-center ga-2 text-medium-emphasis text-caption mb-1">
              <v-icon :icon="tile.icon" size="18" />
              {{ $t(`inventory.indicators.tiles.${tile.key}`) }}
            </div>
            <div class="text-h5 font-weight-bold">{{ tile.value }}</div>
            <div class="text-caption text-medium-emphasis">{{ tile.hint }}</div>
          </v-card>
        </v-col>
      </v-row>

      <v-row>
        <!-- Aging by status -->
        <v-col cols="12" lg="6">
          <v-card class="pa-4 h-100">
            <div class="text-subtitle-1 font-weight-medium">
              {{ $t('inventory.indicators.aging') }}
            </div>
            <div class="text-caption text-medium-emphasis mb-3">
              {{ $t('inventory.indicators.agingHint') }}
            </div>
            <div class="d-flex ga-3 mb-2 text-caption">
              <span v-for="(band, i) in ['0-7', '8-30', '31-90', '91+']" :key="band">
                <v-icon icon="mdi-square" :color="BAND_COLORS[i]" size="12" /> {{ band }}
              </span>
            </div>
            <div v-for="row in data.aging" :key="row.status" class="mb-3" data-testid="aging-row">
              <div class="d-flex justify-space-between text-body-2">
                <span>{{ $t(`inventory.statuses.${row.status}`) }}</span>
                <span class="text-medium-emphasis"
                  >{{ row.total }} ·
                  {{ $t('inventory.indicators.oldest', { n: row.max_days }) }}</span
                >
              </div>
              <div class="stacked">
                <div
                  v-for="(band, i) in ['0-7', '8-30', '31-90', '91+']"
                  :key="band"
                  :class="`bg-${BAND_COLORS[i]}`"
                  :style="{ width: `${((row.bands[band] ?? 0) * 100) / row.total}%` }"
                  :title="`${band}: ${row.bands[band] ?? 0}`"
                />
              </div>
            </div>
            <div v-if="!data.aging.length" class="text-medium-emphasis">
              {{ $t('inventory.indicators.none') }}
            </div>
          </v-card>
        </v-col>

        <!-- Grades -->
        <v-col cols="12" lg="6">
          <v-card class="pa-4 h-100">
            <div class="text-subtitle-1 font-weight-medium mb-3">
              {{ $t('inventory.indicators.grades') }}
            </div>
            <div class="d-flex ga-3 mb-2 text-caption">
              <span v-for="level in GRADE_LEVELS" :key="level">
                <v-icon icon="mdi-square" :color="GRADE_COLORS[level]" size="12" /> {{ level }}
              </span>
            </div>
            <div v-for="row in data.grades" :key="row.asset_class" class="mb-3">
              <div class="d-flex justify-space-between text-body-2">
                <span>{{ row.asset_class }}</span>
                <span class="text-medium-emphasis">{{ row.total }}</span>
              </div>
              <div class="stacked">
                <div
                  v-for="level in GRADE_LEVELS"
                  :key="level"
                  :class="`bg-${GRADE_COLORS[level]}`"
                  :style="{ width: `${((row.levels[level] ?? 0) * 100) / row.total}%` }"
                  :title="`${level}: ${row.levels[level] ?? 0}`"
                />
              </div>
            </div>
            <div v-if="!data.grades.length" class="text-medium-emphasis">
              {{ $t('inventory.indicators.none') }}
            </div>
          </v-card>
        </v-col>

        <!-- Ratios by group -->
        <v-col
          v-for="block in [
            { key: 'scrapByClass', rows: data.scrap_rate.by_asset_class },
            { key: 'scrapByCustomer', rows: data.scrap_rate.by_customer },
            { key: 'divergencesByCustomer', rows: data.divergences.by_customer },
            { key: 'divergencesByLot', rows: data.divergences.by_lot },
            { key: 'withoutSerialByClass', rows: data.without_serial.by_asset_class },
            { key: 'withoutSerialByCustomer', rows: data.without_serial.by_customer },
          ]"
          :key="block.key"
          cols="12"
          md="6"
          lg="4"
        >
          <v-card class="pa-4 h-100" :data-testid="`ratios-${block.key}`">
            <div class="text-subtitle-1 font-weight-medium mb-3">
              {{ $t(`inventory.indicators.blocks.${block.key}`) }}
            </div>
            <div v-for="row in block.rows.slice(0, 8)" :key="row.label" class="mb-2">
              <div class="d-flex justify-space-between text-body-2">
                <span class="text-truncate">{{ row.label }}</span>
                <span class="text-no-wrap"
                  ><strong>{{ pct(row.percent) }}</strong>
                  <span class="text-caption text-medium-emphasis">
                    {{ row.part }}/{{ row.total }}</span
                  ></span
                >
              </div>
              <v-progress-linear :model-value="share(row)" color="primary" height="6" rounded />
            </div>
            <div v-if="!block.rows.length" class="text-medium-emphasis">
              {{ $t('inventory.indicators.none') }}
            </div>
          </v-card>
        </v-col>

        <!-- Lead time by group -->
        <v-col
          v-for="block in [
            { key: 'leadByCustomer', rows: data.lead_time.by_customer },
            { key: 'leadByClass', rows: data.lead_time.by_asset_class },
          ]"
          :key="block.key"
          cols="12"
          md="6"
        >
          <v-card class="pa-4 h-100">
            <div class="text-subtitle-1 font-weight-medium mb-3">
              {{ $t(`inventory.indicators.blocks.${block.key}`) }}
            </div>
            <v-table density="compact">
              <tbody>
                <tr v-for="row in block.rows.slice(0, 10)" :key="row.label">
                  <td>{{ row.label }}</td>
                  <td class="text-right">{{ days(row.average_days) }}</td>
                  <td class="text-right text-medium-emphasis">
                    {{ $t('inventory.indicators.units', { n: row.units }) }}
                  </td>
                </tr>
                <tr v-if="!block.rows.length">
                  <td class="text-medium-emphasis">{{ $t('inventory.indicators.none') }}</td>
                </tr>
              </tbody>
            </v-table>
          </v-card>
        </v-col>

        <!-- Penalties and location accuracy per count -->
        <v-col cols="12" md="6">
          <v-card class="pa-4 h-100" data-testid="penalties">
            <div class="text-subtitle-1 font-weight-medium mb-3">
              {{ $t('inventory.indicators.penalties') }}
            </div>
            <v-table density="compact">
              <tbody>
                <tr
                  v-for="key in ['found', 'chargeable', 'charged', 'cancelled'] as const"
                  :key="key"
                >
                  <td>{{ $t(`inventory.indicators.penaltyKinds.${key}`) }}</td>
                  <td class="text-right font-weight-medium">{{ money(data.penalties[key]) }}</td>
                </tr>
              </tbody>
            </v-table>
          </v-card>
        </v-col>
        <v-col cols="12" md="6">
          <v-card class="pa-4 h-100">
            <div class="text-subtitle-1 font-weight-medium mb-3">
              {{ $t('inventory.indicators.accuracyByCount') }}
            </div>
            <v-table density="compact">
              <tbody>
                <tr v-for="row in data.location_accuracy.counts" :key="row.count">
                  <td>{{ row.count }} · {{ row.warehouse }}</td>
                  <td class="text-right">{{ row.matched }}/{{ row.expected }}</td>
                  <td class="text-right font-weight-medium">{{ pct(row.percent) }}</td>
                </tr>
                <tr v-if="!data.location_accuracy.counts.length">
                  <td class="text-medium-emphasis">{{ $t('inventory.indicators.none') }}</td>
                </tr>
              </tbody>
            </v-table>
          </v-card>
        </v-col>
      </v-row>
    </template>
  </v-container>
</template>

<style scoped>
.stacked {
  display: flex;
  height: 10px;
  border-radius: 5px;
  overflow: hidden;
  background: rgba(var(--v-theme-on-surface), 0.08);
  margin-top: 4px;
}
</style>
