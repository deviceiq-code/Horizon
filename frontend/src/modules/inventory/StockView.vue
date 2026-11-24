<script setup lang="ts">
/**
 * The stock query: assets grouped by asset class × model × grade × status × warehouse (units,
 * average and longest days in stock). A group expands to its units with their current report's
 * data — functioning, conservation, completeness, missing items — and the disposal holding them.
 */
import { computed, onMounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useDateFormat } from '@/composables/useDateFormat'
import { listWarehouses, type Warehouse } from '@/modules/warehouses/api'
import CustomerSelect from './CustomerSelect.vue'
import StatusChip from './StatusChip.vue'
import {
  ASSET_STATUSES,
  stockAssets,
  stockGroups,
  type StockAsset,
  type StockFilters,
  type StockGroup,
} from './api'

const { t } = useI18n()
const { d } = useDateFormat()

const warehouses = ref<Warehouse[]>([])
const warehouse = ref<number | null>(null)
const status = ref<string>('available')
const customer = ref<number | null>(null)
const minDays = ref('')
const search = ref('')
const groups = ref<StockGroup[]>([])
const loading = ref(false)
const failed = ref(false)

const statusOptions = computed(() => [
  { value: 'all', title: t('inventory.stock.allStatuses') },
  ...ASSET_STATUSES.filter((s) => s !== 'written_off').map((value) => ({
    value,
    title: t(`inventory.statuses.${value}`),
  })),
])
const warehouseOptions = computed(() => [
  { value: null, title: t('common.filters.all') },
  ...warehouses.value.map((w) => ({ value: w.id, title: `${w.code} · ${w.name}` })),
])

const filters = computed<StockFilters>(() => ({
  status: status.value,
  warehouse: warehouse.value,
  customer: customer.value,
  min_days: /^\d+$/.test(minDays.value.trim()) ? minDays.value.trim() : null,
  search: search.value.trim(),
}))

async function load() {
  loading.value = true
  failed.value = false
  expanded.value = []
  try {
    groups.value = await stockGroups(filters.value)
  } catch {
    failed.value = true
    groups.value = []
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
let timer: ReturnType<typeof setTimeout> | undefined
watch([warehouse, status, customer], load)
watch([minDays, search], () => {
  clearTimeout(timer)
  timer = setTimeout(load, 400)
})

const totalUnits = computed(() => groups.value.reduce((sum, g) => sum + g.units, 0))

// --- A group's units -----------------------------------------------------------------------------

const groupKey = (g: StockGroup) => `${g.asset_model}|${g.grade}|${g.status}|${g.warehouse}`
const expanded = ref<string[]>([])
const units = ref<Record<string, StockAsset[] | 'loading' | 'error'>>({})

async function toggle(group: StockGroup) {
  const key = groupKey(group)
  if (expanded.value.includes(key)) {
    expanded.value = expanded.value.filter((k) => k !== key)
    return
  }
  expanded.value = [...expanded.value, key]
  units.value[key] = 'loading'
  try {
    units.value[key] = (
      await stockAssets(
        {
          ...filters.value,
          status: group.status,
          warehouse: group.warehouse,
          asset_model: group.asset_model,
          grade: group.grade,
        },
        1,
        200,
      )
    ).results
  } catch {
    units.value[key] = 'error'
  }
}

function unitsOf(group: StockGroup): StockAsset[] {
  const value = units.value[groupKey(group)]
  return Array.isArray(value) ? value : []
}

const reportCode = (a: StockAsset) =>
  a.report ? `${a.report.conservation}${a.report.functioning}${a.report.completeness}` : '—'
</script>

<template>
  <v-container fluid class="module-page">
    <h1 class="mb-1">{{ $t('inventory.stock.title') }}</h1>
    <p class="text-medium-emphasis mb-4">{{ $t('inventory.stock.subtitle') }}</p>

    <v-row dense class="mb-2">
      <v-col cols="12" sm="6" md="2">
        <v-select
          v-model="status"
          :items="statusOptions"
          :label="$t('inventory.fields.status')"
          density="compact"
          hide-details
          data-testid="stock-status"
        />
      </v-col>
      <v-col cols="12" sm="6" md="3">
        <v-select
          v-model="warehouse"
          :items="warehouseOptions"
          :label="$t('inventory.fields.warehouse')"
          density="compact"
          hide-details
        />
      </v-col>
      <v-col cols="12" sm="6" md="3">
        <CustomerSelect
          v-model="customer"
          :label="$t('inventory.stock.originCustomer')"
          density="compact"
          hide-details
          clearable
        />
      </v-col>
      <v-col cols="6" sm="3" md="1">
        <v-text-field
          v-model="minDays"
          :label="$t('inventory.stock.minDays')"
          inputmode="numeric"
          density="compact"
          hide-details
          data-testid="stock-min-days"
        />
      </v-col>
      <v-col cols="12" sm="9" md="3">
        <v-text-field
          v-model="search"
          :placeholder="$t('inventory.stock.searchPlaceholder')"
          prepend-inner-icon="mdi-magnify"
          density="compact"
          hide-details
          clearable
          @click:clear="search = ''"
        />
      </v-col>
    </v-row>

    <v-card :loading="loading">
      <v-table density="comfortable" data-testid="stock-groups">
        <thead>
          <tr>
            <th style="width: 40px" />
            <th>{{ $t('inventory.fields.assetClass') }}</th>
            <th>{{ $t('inventory.fields.assetModel') }}</th>
            <th>{{ $t('inventory.stock.grade') }}</th>
            <th>{{ $t('inventory.fields.status') }}</th>
            <th>{{ $t('inventory.fields.warehouse') }}</th>
            <th class="text-right">{{ $t('inventory.stock.units') }}</th>
            <th class="text-right">{{ $t('inventory.stock.averageDays') }}</th>
            <th class="text-right">{{ $t('inventory.stock.maxDays') }}</th>
          </tr>
        </thead>
        <tbody>
          <template v-for="g in groups" :key="groupKey(g)">
            <tr class="stock-group" data-testid="stock-group" @click="toggle(g)">
              <td>
                <v-icon
                  :icon="expanded.includes(groupKey(g)) ? 'mdi-chevron-down' : 'mdi-chevron-right'"
                  size="small"
                />
              </td>
              <td>{{ g.asset_class_name }}</td>
              <td class="font-weight-medium">{{ g.model }}</td>
              <td>
                <v-chip v-if="g.grade" size="small" label variant="outlined">{{ g.grade }}</v-chip>
                <span v-else class="text-medium-emphasis">—</span>
              </td>
              <td><StatusChip :status="g.status" /></td>
              <td>{{ g.warehouse_code }}</td>
              <td class="text-right font-weight-medium">{{ $n(g.units) }}</td>
              <td class="text-right">{{ $n(g.average_days) }}</td>
              <td class="text-right">{{ $n(g.max_days) }}</td>
            </tr>
            <tr v-if="expanded.includes(groupKey(g))" class="stock-units">
              <td colspan="9" class="pa-0">
                <v-progress-linear v-if="units[groupKey(g)] === 'loading'" indeterminate />
                <div v-else-if="units[groupKey(g)] === 'error'" class="pa-3 text-error">
                  {{ $t('common.loadError') }}
                </div>
                <v-table v-else density="compact" class="bg-transparent" data-testid="stock-units">
                  <thead>
                    <tr>
                      <th>{{ $t('inventory.fields.horizonId') }}</th>
                      <th>{{ $t('inventory.fields.serial') }}</th>
                      <th>{{ $t('inventory.fields.location') }}</th>
                      <th>{{ $t('inventory.stock.originCustomer') }}</th>
                      <th>{{ $t('inventory.stock.report') }}</th>
                      <th>{{ $t('inventory.stock.missingItems') }}</th>
                      <th>{{ $t('inventory.fields.enteredAt') }}</th>
                      <th class="text-right">{{ $t('inventory.stock.daysInStock') }}</th>
                      <th>{{ $t('inventory.disposals.disposal') }}</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr v-for="a in unitsOf(g)" :key="a.id" data-testid="stock-unit">
                      <td class="font-weight-medium">
                        {{ a.horizon_id }}
                        <v-icon
                          v-if="a.held_for_dispute"
                          icon="mdi-lock-outline"
                          size="x-small"
                          :title="$t('inventory.heldForDispute')"
                        />
                      </td>
                      <td>{{ a.serial || '—' }}</td>
                      <td>{{ a.location }}</td>
                      <td>{{ a.customer ?? '—' }}</td>
                      <td>
                        <router-link
                          v-if="a.report"
                          :to="{ name: 'inventory-report', params: { id: a.report.id } }"
                          >{{ reportCode(a) }} · v{{ a.report.version }}</router-link
                        >
                        <span v-else class="text-medium-emphasis">—</span>
                      </td>
                      <td>{{ a.report?.missing_items.join(', ') || '—' }}</td>
                      <td>{{ d(new Date(a.created_at), 'short') }}</td>
                      <td class="text-right">{{ $n(a.days_in_stock) }}</td>
                      <td>
                        <router-link
                          v-if="a.disposal"
                          :to="{ name: 'inventory-disposal', params: { id: a.disposal.id } }"
                          >{{ a.disposal.code }}</router-link
                        >
                        <span v-else class="text-medium-emphasis">—</span>
                      </td>
                    </tr>
                  </tbody>
                </v-table>
              </td>
            </tr>
          </template>
          <tr v-if="!groups.length && !loading">
            <td colspan="9" class="text-medium-emphasis">
              {{ failed ? $t('common.loadError') : $t('inventory.stock.empty') }}
            </td>
          </tr>
        </tbody>
        <tfoot v-if="groups.length">
          <tr>
            <td colspan="6" class="text-right text-medium-emphasis">
              {{ $t('inventory.stock.total') }}
            </td>
            <td class="text-right font-weight-bold" data-testid="stock-total">
              {{ $n(totalUnits) }}
            </td>
            <td colspan="2" />
          </tr>
        </tfoot>
      </v-table>
    </v-card>
  </v-container>
</template>

<style scoped>
.stock-group {
  cursor: pointer;
}
.stock-units > td {
  background: rgba(var(--v-theme-on-surface), 0.03);
}
</style>
