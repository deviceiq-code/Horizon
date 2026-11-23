<script setup lang="ts">
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import ServerCrudTable from '@/components/ServerCrudTable.vue'
import { useColumnFilters } from '@/composables/useColumnFilters'
import { useNotificationsStore } from '@/stores/notifications'
import EnabledChip from '../EnabledChip.vue'
import RemarketingAverage from '../remarketing/RemarketingAverage.vue'
import ManufacturerFormDialog from './ManufacturerFormDialog.vue'
import {
  deleteManufacturer,
  listManufacturers,
  MANUFACTURER_RATINGS,
  type Manufacturer,
} from './api'

const { t } = useI18n()
const notifications = useNotificationsStore()

const table = ref<{ reload: () => Promise<void> } | null>(null)

// --- Column filters --------------------------------------------------------------------------

const {
  filters,
  typed,
  clear: clearFilters,
} = useColumnFilters(['name', 'remarketing_min', 'is_enabled'] as const, ['name'] as const)
const starOptions = [1, 2, 3, 4, 5].map((stars) => ({ value: stars, title: `★ ${stars}+` }))
const statusOptions = computed(() => [
  { value: 'true', title: t('catalogs.status.enabled') },
  { value: 'false', title: t('catalogs.status.disabled') },
])

const headers = computed(() => [
  { title: t('catalogs.fields.id'), key: 'id', width: 80 },
  { title: t('manufacturers.fields.name'), key: 'name', minWidth: '220px' },
  // Average of the three ratings; hover for each one
  { title: t('manufacturers.remarketing.title'), key: 'remarketing_average', width: 230 },
  { title: t('catalogs.fields.status'), key: 'is_enabled', width: 150 },
])

const formOpen = ref(false)
const editing = ref<Manufacturer | null>(null)

function openForm(manufacturer: Manufacturer | null) {
  editing.value = manufacturer
  formOpen.value = true
}

function onSaved(_manufacturer: Manufacturer, created: boolean) {
  notifications.notify(t(created ? 'manufacturers.created' : 'manufacturers.updated'))
  table.value?.reload()
}
</script>

<template>
  <ServerCrudTable
    ref="table"
    :fetch-page="listManufacturers"
    :delete-item="deleteManufacturer"
    :headers="headers"
    :sort-by="[{ key: 'name', order: 'asc' }]"
    :ordering-fields="{ remarketing_average: 'remarketing_score' }"
    :search-placeholder="$t('manufacturers.searchPlaceholder')"
    :filters="filters"
    filters-storage-key="manufacturers"
    :empty-text="$t('manufacturers.empty')"
    :no-results-text="$t('manufacturers.noResults')"
    :delete-title="$t('manufacturers.deleteTitle')"
    :delete-message="(m: Manufacturer) => $t('manufacturers.deleteConfirm', { name: m.name })"
    :deleted-text="$t('manufacturers.deleted')"
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
    <template #[`filter.remarketing_average`]>
      <v-select
        v-model="filters.remarketing_min"
        :items="starOptions"
        :placeholder="$t('assetClasses.filters.minStars')"
        density="compact"
        hide-details
        clearable
        data-testid="filter-stars"
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
    <template #[`item.remarketing_average`]="{ item }">
      <RemarketingAverage
        :average="item.remarketing_average"
        :breakdown="
          MANUFACTURER_RATINGS.map((field) => ({
            label: $t(`manufacturers.remarketing.${field}.label`),
            value: item[field],
          }))
        "
      />
    </template>
    <template #[`item.is_enabled`]="{ item }">
      <EnabledChip :enabled="item.is_enabled" />
    </template>
  </ServerCrudTable>

  <ManufacturerFormDialog v-model="formOpen" :manufacturer="editing" @saved="onSaved" />
</template>
