<script setup lang="ts">
/** Balances of accessories controlled by quantity (cables, chargers…) per container or
 * location, in good condition or as scrap. They change only through triage and movements. */
import { computed, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import ServerCrudTable from '@/components/ServerCrudTable.vue'
import { useColumnFilters } from '@/composables/useColumnFilters'
import { listWarehouses, type Warehouse } from '@/modules/warehouses/api'
import AreaChip from './AreaChip.vue'
import { listAccessoryBalances } from './api'

const { t } = useI18n()

const { filters, clear: clearFilters } = useColumnFilters(['condition', 'warehouse'] as const, [])
const warehouses = ref<Warehouse[]>([])
onMounted(async () => {
  try {
    warehouses.value = (await listWarehouses({ page: 1, pageSize: 200, ordering: 'name' })).results
  } catch {
    warehouses.value = []
  }
})
const conditionOptions = computed(() =>
  (['good', 'scrap'] as const).map((value) => ({
    value,
    title: t(`inventory.accessories.conditions.${value}`),
  })),
)
const warehouseOptions = computed(() =>
  warehouses.value.map((w) => ({ value: w.id, title: `${w.code} · ${w.name}` })),
)
const headers = computed(() => [
  { title: t('inventory.fields.assetModel'), key: 'asset_model__name' },
  { title: t('inventory.expected.quantity'), key: 'quantity', width: 130 },
  { title: t('inventory.accessories.condition'), key: 'condition', width: 150 },
  { title: t('inventory.fields.warehouse'), key: 'warehouse', sortable: false, width: 140 },
  { title: t('inventory.fields.location'), key: 'place', sortable: false },
])
</script>

<template>
  <ServerCrudTable
    :fetch-page="listAccessoryBalances"
    :delete-item="async () => undefined"
    :headers="headers"
    :sort-by="[{ key: 'asset_model__name', order: 'asc' }]"
    :search-placeholder="$t('inventory.accessories.searchPlaceholder')"
    :filters="filters"
    filters-storage-key="inventory-accessories"
    :empty-text="$t('inventory.accessories.empty')"
    :no-results-text="$t('inventory.accessories.noResults')"
    delete-title=""
    :delete-message="() => ''"
    deleted-text=""
    hide-create
    :can-edit="() => false"
    :can-delete="() => false"
    @clear-filters="clearFilters"
  >
    <template #[`filter.condition`]>
      <v-select
        v-model="filters.condition"
        :items="conditionOptions"
        :placeholder="$t('common.filters.all')"
        density="compact"
        hide-details
        clearable
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
      />
    </template>
    <template #[`item.asset_model__name`]="{ item }">
      <div class="py-2">
        <div>{{ item.asset_model_label }}</div>
        <div class="text-caption text-medium-emphasis">{{ item.asset_class_name }}</div>
      </div>
    </template>
    <template #[`item.quantity`]="{ item }">
      <strong>{{ item.quantity }}</strong>
    </template>
    <template #[`item.condition`]="{ item }">
      <v-chip
        :color="item.condition === 'good' ? 'success' : undefined"
        size="small"
        variant="tonal"
        label
      >
        {{ $t(`inventory.accessories.conditions.${item.condition}`) }}
      </v-chip>
    </template>
    <template #[`item.warehouse`]="{ item }">{{ item.warehouse?.code ?? '—' }}</template>
    <template #[`item.place`]="{ item }">
      <span class="d-inline-flex align-center ga-2">
        {{ item.location_detail.code }}
        <AreaChip :area="item.location_detail.area_type" size="x-small" />
        <span v-if="item.container_code" class="text-caption">· {{ item.container_code }}</span>
      </span>
    </template>
  </ServerCrudTable>
</template>
