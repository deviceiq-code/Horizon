<script setup lang="ts">
/** Asset models (Administration › Catalogs): a manufacturer's model of an asset class, as
 * Asset Classes' page (column filters). */
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import ServerCrudTable from '@/components/ServerCrudTable.vue'
import { useColumnFilters } from '@/composables/useColumnFilters'
import { useNumberFormat } from '@/composables/useNumberFormat'
import { specSummary } from '@/modules/average-prices/specText'
import { useNotificationsStore } from '@/stores/notifications'
import EnabledChip from '../EnabledChip.vue'
import AssetModelFormDialog from './AssetModelFormDialog.vue'
import { deleteAssetModel, listAssetModels, type AssetModel } from './api'

const { t } = useI18n()
const { n } = useNumberFormat()
const notifications = useNotificationsStore()

const table = ref<{ reload: () => Promise<void> } | null>(null)

// --- Column filters --------------------------------------------------------------------------

const {
  filters,
  typed,
  clear: clearFilters,
} = useColumnFilters(['name', 'tracking', 'is_enabled'] as const, ['name'] as const)
const trackingOptions = computed(() => [
  { value: 'unit', title: t('assetModels.tracking.unit') },
  { value: 'quantity', title: t('assetModels.tracking.quantity') },
])
const statusOptions = computed(() => [
  { value: 'true', title: t('catalogs.status.enabled') },
  { value: 'false', title: t('catalogs.status.disabled') },
])

const headers = computed(() => [
  { title: t('catalogs.fields.id'), key: 'id', width: 80 },
  { title: t('assetModels.fields.name'), key: 'name', minWidth: '240px' },
  { title: t('assetModels.fields.assetClass'), key: 'asset_class_detail', sortable: false },
  { title: t('assetModels.fields.tracking'), key: 'tracking', width: 180 },
  { title: t('assetModels.fields.inStock'), key: 'assets_count', sortable: false, width: 120 },
  { title: t('catalogs.fields.status'), key: 'is_enabled', width: 150 },
])

const formOpen = ref(false)
const editing = ref<AssetModel | null>(null)

function openForm(assetModel: AssetModel | null) {
  editing.value = assetModel
  formOpen.value = true
}

function onSaved(_assetModel: AssetModel, created: boolean) {
  notifications.notify(t(created ? 'assetModels.created' : 'assetModels.updated'))
  table.value?.reload()
}
</script>

<template>
  <ServerCrudTable
    ref="table"
    :fetch-page="listAssetModels"
    :delete-item="deleteAssetModel"
    :headers="headers"
    :sort-by="[{ key: 'name', order: 'asc' }]"
    :search-placeholder="$t('assetModels.searchPlaceholder')"
    :filters="filters"
    filters-storage-key="asset-models"
    :empty-text="$t('assetModels.empty')"
    :no-results-text="$t('assetModels.noResults')"
    :delete-title="$t('assetModels.deleteTitle')"
    :delete-message="
      (m: AssetModel) =>
        $t('assetModels.deleteConfirm', { name: `${m.manufacturer_name} ${m.name}` })
    "
    :deleted-text="$t('assetModels.deleted')"
    @clear-filters="clearFilters"
    @create="openForm(null)"
    @edit="openForm"
  >
    <template #[`filter.name`]>
      <v-text-field
        v-model="typed.name"
        :placeholder="$t('assetModels.filters.name')"
        prepend-inner-icon="mdi-filter-outline"
        density="compact"
        hide-details
        clearable
        data-testid="filter-name"
      />
    </template>
    <template #[`filter.tracking`]>
      <v-select
        v-model="filters.tracking"
        :items="trackingOptions"
        :placeholder="$t('common.filters.all')"
        density="compact"
        hide-details
        clearable
        data-testid="filter-tracking"
      />
    </template>
    <template #[`filter.is_enabled`]>
      <v-select
        v-model="filters.is_enabled"
        :items="statusOptions"
        :placeholder="$t('common.filters.all')"
        density="compact"
        hide-details
        clearable
        data-testid="filter-status"
      />
    </template>
    <template #[`item.name`]="{ item }">
      <div class="py-2">
        <div>
          <span class="text-medium-emphasis">{{ item.manufacturer_name }}</span>
          {{ item.name }}
        </div>
        <div
          v-if="specSummary(item.spec_values, t, n)"
          class="text-caption text-medium-emphasis text-truncate"
          style="max-width: 360px"
          data-testid="specs-preview"
        >
          {{ specSummary(item.spec_values, t, n) }}
        </div>
      </div>
    </template>
    <template #[`item.asset_class_detail`]="{ item }">
      <span class="d-inline-flex align-center ga-2">
        <v-icon :icon="item.asset_class_detail.icon" size="18" color="primary" />
        {{ item.asset_class_detail.name }}
      </span>
    </template>
    <template #[`item.tracking`]="{ item }">
      <div class="d-flex flex-wrap ga-1">
        <v-chip size="small" variant="tonal" label>
          {{ $t(`assetModels.tracking.${item.tracking}`) }}
        </v-chip>
        <v-chip
          v-if="item.has_storage"
          size="small"
          variant="tonal"
          color="warning"
          label
          prepend-icon="mdi-harddisk"
          :title="$t('assetModels.fields.hasStorage')"
        >
          {{ $t('assetModels.storage') }}
        </v-chip>
      </div>
    </template>
    <template #[`item.is_enabled`]="{ item }">
      <EnabledChip :enabled="item.is_enabled" />
    </template>
  </ServerCrudTable>

  <AssetModelFormDialog v-model="formOpen" :asset-model="editing" @saved="onSaved" />
</template>
