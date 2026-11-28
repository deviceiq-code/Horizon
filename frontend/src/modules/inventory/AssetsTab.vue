<script setup lang="ts">
/** Assets in stock (Asset Management › Inventory): grid with column filters and the detail with the
 * whole history. Assets enter through the triage of receiving lots and are never deleted. */
import { computed, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import ServerCrudTable from '@/components/ServerCrudTable.vue'
import { useColumnFilters } from '@/composables/useColumnFilters'
import { listWarehouses, type Warehouse } from '@/modules/warehouses/api'
import AreaChip from './AreaChip.vue'
import AssetDetailDialog from './AssetDetailDialog.vue'
import StatusChip from './StatusChip.vue'
import { ASSET_STATUSES, listAssets, type Asset } from './api'

const { t } = useI18n()

const table = ref<{ reload: () => Promise<void> } | null>(null)

// --- Column filters --------------------------------------------------------------------------

const {
  filters,
  typed,
  clear: clearFilters,
} = useColumnFilters(['name', 'status', 'warehouse'] as const, ['name'] as const)
const warehouses = ref<Warehouse[]>([])
onMounted(async () => {
  try {
    warehouses.value = (await listWarehouses({ page: 1, pageSize: 200, ordering: 'name' })).results
  } catch {
    // The grid works without this filter's options
  }
})
const statusOptions = computed(() =>
  ASSET_STATUSES.map((status) => ({ value: status, title: t(`inventory.statuses.${status}`) })),
)
const warehouseOptions = computed(() =>
  warehouses.value.map((w) => ({ value: w.id, title: `${w.code} · ${w.name}` })),
)

const headers = computed(() => [
  { title: t('inventory.fields.horizonId'), key: 'horizon_id', width: 150 },
  { title: t('inventory.fields.asset'), key: 'asset_model__name', minWidth: '240px' },
  { title: t('inventory.fields.status'), key: 'status', width: 200 },
  { title: t('inventory.fields.warehouse'), key: 'warehouse', sortable: false, width: 180 },
  { title: t('inventory.fields.location'), key: 'current_location__code' },
])

// --- Detail ---------------------------------------------------------------------------------------

const detailOpen = ref(false)
const shown = ref<Asset | null>(null)

function openDetail(asset: Asset) {
  shown.value = asset
  detailOpen.value = true
}
</script>

<template>
  <ServerCrudTable
    ref="table"
    :fetch-page="listAssets"
    :delete-item="async () => undefined"
    :headers="headers"
    :sort-by="[{ key: 'horizon_id', order: 'desc' }]"
    :search-placeholder="$t('inventory.assets.searchPlaceholder')"
    :filters="filters"
    filters-storage-key="inventory-assets"
    :empty-text="$t('inventory.assets.empty')"
    :no-results-text="$t('inventory.assets.noResults')"
    delete-title=""
    :delete-message="() => ''"
    deleted-text=""
    hide-create
    :can-delete="() => false"
    edit-icon="mdi-eye-outline"
    :edit-title="$t('inventory.assets.details')"
    @clear-filters="clearFilters"
    @edit="openDetail"
  >
    <template #[`filter.asset_model__name`]>
      <v-text-field
        v-model="typed.name"
        :placeholder="$t('inventory.assets.filterName')"
        prepend-inner-icon="mdi-filter-outline"
        density="compact"
        hide-details
        clearable
        data-testid="filter-name"
      />
    </template>
    <template #[`filter.status`]>
      <v-select
        v-model="filters.status"
        :items="statusOptions"
        :placeholder="$t('common.filters.all')"
        density="compact"
        hide-details
        clearable
        data-testid="filter-status"
      />
    </template>
    <template #[`filter.warehouse`]>
      <v-select
        v-model="filters.warehouse"
        :items="warehouseOptions"
        :placeholder="$t('common.filters.all')"
        density="compact"
        hide-details
        clearable
        data-testid="filter-warehouse"
      />
    </template>
    <template #[`item.horizon_id`]="{ item }">
      <span class="font-weight-medium text-no-wrap">{{ item.horizon_id }}</span>
    </template>
    <template #[`item.asset_model__name`]="{ item }">
      <div class="d-flex align-center ga-3 py-2">
        <v-icon :icon="item.asset_model_detail.asset_class_icon" color="primary" />
        <div>
          <div>
            {{ item.asset_model_detail.manufacturer_name }} {{ item.asset_model_detail.name }}
          </div>
          <div class="text-caption text-medium-emphasis">
            {{ $t('inventory.fields.serial') }}:
            {{ item.serial || $t(`inventory.serialStatus.${item.serial_status}`) }}
          </div>
        </div>
      </div>
    </template>
    <template #[`item.status`]="{ item }">
      <StatusChip :status="item.status" :held="item.held_for_dispute" />
    </template>
    <template #[`item.warehouse`]="{ item }">
      <span v-if="item.warehouse" :title="item.warehouse.name">{{ item.warehouse.code }}</span>
      <span v-else class="text-medium-emphasis">—</span>
    </template>
    <template #[`item.current_location__code`]="{ item }">
      <div class="d-flex align-center flex-wrap ga-2 py-1">
        <span class="text-no-wrap">{{ item.current_location_detail.code }}</span>
        <AreaChip :area="item.current_location_detail.area_type" size="x-small" />
        <span v-if="item.current_container_detail" class="text-caption text-medium-emphasis">
          {{ item.current_container_detail.code }}
        </span>
      </div>
    </template>
  </ServerCrudTable>

  <AssetDetailDialog
    v-model="detailOpen"
    :asset-id="shown?.id ?? null"
    @changed="table?.reload()"
  />
</template>
