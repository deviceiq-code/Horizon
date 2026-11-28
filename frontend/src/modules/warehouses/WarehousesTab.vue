<script setup lang="ts">
/** Warehouses (Asset Management › Inventory): grid with column filters, as the catalogs'. */
import { computed, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import ActiveChip from '@/components/ActiveChip.vue'
import ServerCrudTable from '@/components/ServerCrudTable.vue'
import { useColumnFilters } from '@/composables/useColumnFilters'
import { listVerticals, type VerticalRef } from '@/modules/catalogs/verticals/api'
import { useNotificationsStore } from '@/stores/notifications'
import WarehouseFormDialog from './WarehouseFormDialog.vue'
import { deleteWarehouse, listWarehouses, type Warehouse } from './api'

const { t } = useI18n()
const notifications = useNotificationsStore()

const table = ref<{ reload: () => Promise<void> } | null>(null)

// --- Column filters --------------------------------------------------------------------------

const {
  filters,
  typed,
  clear: clearFilters,
} = useColumnFilters(
  ['name', 'ownership', 'vertical', 'location', 'is_active'] as const,
  ['name', 'location'] as const,
)
const ownershipOptions = computed(() => [
  { value: 'own', title: t('warehouses.ownership.own') },
  { value: 'outsourced', title: t('warehouses.ownership.outsourced') },
])
const verticals = ref<VerticalRef[]>([])
onMounted(async () => {
  try {
    verticals.value = (await listVerticals({ page: 1, pageSize: 200, ordering: 'name' })).results
  } catch {
    // The grid works without this filter's options
  }
})
const statusOptions = computed(() => [
  { value: 'true', title: t('customers.status.active') },
  { value: 'false', title: t('customers.status.inactive') },
])

const headers = computed(() => [
  { title: t('warehouses.fields.code'), key: 'code', width: 110 },
  { title: t('warehouses.fields.name'), key: 'name', minWidth: '220px' },
  { title: t('warehouses.fields.ownership'), key: 'ownership', minWidth: '240px' },
  { title: t('warehouses.fields.verticals'), key: 'verticals_detail', sortable: false },
  { title: t('customers.fields.location'), key: 'city', width: 200 },
  { title: t('warehouses.fields.contact'), key: 'contact_name', sortable: false },
  { title: t('customers.fields.status'), key: 'is_active', width: 150 },
])

function location(w: Warehouse): string {
  return [w.city, w.state].filter(Boolean).join(' / ')
}

const formOpen = ref(false)
const editing = ref<Warehouse | null>(null)

function openForm(warehouse: Warehouse | null) {
  editing.value = warehouse
  formOpen.value = true
}

function onSaved(_warehouse: Warehouse, created: boolean) {
  notifications.notify(t(created ? 'warehouses.created' : 'warehouses.updated'))
  table.value?.reload()
}
</script>

<template>
  <ServerCrudTable
    ref="table"
    :fetch-page="listWarehouses"
    :delete-item="deleteWarehouse"
    :headers="headers"
    :sort-by="[{ key: 'name', order: 'asc' }]"
    :search-placeholder="$t('warehouses.searchPlaceholder')"
    :filters="filters"
    filters-storage-key="warehouses"
    :empty-text="$t('warehouses.empty')"
    :no-results-text="$t('warehouses.noResults')"
    :delete-title="$t('warehouses.deleteTitle')"
    :delete-message="(w: Warehouse) => $t('warehouses.deleteConfirm', { name: w.name })"
    :deleted-text="$t('warehouses.deleted')"
    @clear-filters="clearFilters"
    @create="openForm(null)"
    @edit="openForm"
  >
    <template #[`filter.name`]>
      <v-text-field
        v-model="typed.name"
        :placeholder="$t('common.filters.nameOrKeyword')"
        prepend-inner-icon="mdi-filter-outline"
        density="compact"
        hide-details
        clearable
        data-testid="filter-name"
      />
    </template>
    <template #[`filter.ownership`]>
      <v-select
        v-model="filters.ownership"
        :items="ownershipOptions"
        :placeholder="$t('common.filters.all')"
        density="compact"
        hide-details
        clearable
        data-testid="filter-ownership"
      />
    </template>
    <template #[`filter.verticals_detail`]>
      <v-autocomplete
        v-model="filters.vertical"
        :items="verticals"
        item-title="name"
        item-value="id"
        :placeholder="$t('common.filters.all')"
        density="compact"
        hide-details
        clearable
        data-testid="filter-vertical"
      />
    </template>
    <template #[`filter.city`]>
      <v-text-field
        v-model="typed.location"
        :placeholder="$t('customers.fields.location')"
        density="compact"
        hide-details
        clearable
        data-testid="filter-location"
      />
    </template>
    <template #[`filter.is_active`]>
      <v-select
        v-model="filters.is_active"
        :items="statusOptions"
        :placeholder="$t('common.filters.all')"
        density="compact"
        hide-details
        clearable
        data-testid="filter-status"
      />
    </template>
    <template #[`item.code`]="{ item }">
      <span class="font-weight-medium">{{ item.code }}</span>
    </template>
    <template #[`item.name`]="{ item }">
      <div class="py-2">
        <div>{{ item.name }}</div>
        <div
          v-if="item.keywords.length"
          class="text-caption text-medium-emphasis text-truncate"
          style="max-width: 260px"
          :title="item.keywords.join(', ')"
        >
          {{ item.keywords.join(', ') }}
        </div>
      </div>
    </template>
    <template #[`item.ownership`]="{ item }">
      <div class="d-flex align-center flex-wrap ga-2 py-1">
        <v-chip
          :color="item.ownership === 'own' ? 'primary' : 'secondary'"
          :prepend-icon="
            item.ownership === 'own' ? 'mdi-home-city-outline' : 'mdi-handshake-outline'
          "
          size="small"
          variant="tonal"
          label
          data-testid="ownership"
        >
          {{ $t(`warehouses.ownership.${item.ownership}`) }}
        </v-chip>
        <span v-if="item.service_provider_detail" class="text-body-2" data-testid="provider">
          {{ item.service_provider_detail.name }}
        </span>
      </div>
    </template>
    <template #[`item.verticals_detail`]="{ item }">
      <div class="d-flex flex-wrap ga-1 py-1" data-testid="verticals-cell">
        <v-chip
          v-for="vertical in (item as Warehouse).verticals_detail"
          :key="vertical.id"
          size="x-small"
          variant="tonal"
          label
        >
          {{ vertical.name }}
        </v-chip>
      </div>
    </template>
    <template #[`item.city`]="{ item }">{{ location(item) }}</template>
    <template #[`item.contact_name`]="{ item }">
      <div>{{ item.contact_name }}</div>
      <div v-if="item.phone || item.email" class="text-caption text-medium-emphasis">
        {{ [item.phone, item.email].filter(Boolean).join(' · ') }}
      </div>
    </template>
    <template #[`item.is_active`]="{ item }">
      <ActiveChip :active="item.is_active" />
    </template>
  </ServerCrudTable>

  <WarehouseFormDialog v-model="formOpen" :warehouse="editing" @saved="onSaved" />
</template>
