<script setup lang="ts">
/** Service providers (Administration › Catalogs): grid with column filters, as Asset Classes'. */
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import ActiveChip from '@/components/ActiveChip.vue'
import ServerCrudTable from '@/components/ServerCrudTable.vue'
import { useColumnFilters } from '@/composables/useColumnFilters'
import { formatTaxId } from '@/modules/customers/format'
import { useNotificationsStore } from '@/stores/notifications'
import ServiceProviderFormDialog from './ServiceProviderFormDialog.vue'
import {
  deleteServiceProvider,
  listServiceProviders,
  SERVICE_ICONS,
  SERVICE_KINDS,
  type ServiceProvider,
} from './api'

const { t } = useI18n()
const notifications = useNotificationsStore()

const table = ref<{ reload: () => Promise<void> } | null>(null)

// --- Column filters --------------------------------------------------------------------------

const {
  filters,
  typed,
  clear: clearFilters,
} = useColumnFilters(
  ['name', 'tax_id', 'service', 'location', 'is_active'] as const,
  ['name', 'tax_id', 'location'] as const,
)
const serviceOptions = computed(() =>
  SERVICE_KINDS.map((kind) => ({ value: kind, title: t(`serviceProviders.services.${kind}`) })),
)
const statusOptions = computed(() => [
  { value: 'true', title: t('customers.status.active') },
  { value: 'false', title: t('customers.status.inactive') },
])

const headers = computed(() => [
  { title: t('serviceProviders.fields.id'), key: 'id', width: 80 },
  { title: t('serviceProviders.fields.name'), key: 'name', minWidth: '240px' },
  { title: t('serviceProviders.fields.taxId'), key: 'tax_id', width: 200 },
  { title: t('serviceProviders.fields.services'), key: 'services', sortable: false },
  { title: t('serviceProviders.fields.location'), key: 'city', width: 200 },
  { title: t('serviceProviders.fields.status'), key: 'is_active', width: 150 },
])

function location(p: ServiceProvider): string {
  return [p.city, p.state].filter(Boolean).join(' / ')
}

const formOpen = ref(false)
const editing = ref<ServiceProvider | null>(null)

function openForm(provider: ServiceProvider | null) {
  editing.value = provider
  formOpen.value = true
}

function onSaved(_provider: ServiceProvider, created: boolean) {
  notifications.notify(t(created ? 'serviceProviders.created' : 'serviceProviders.updated'))
  table.value?.reload()
}
</script>

<template>
  <ServerCrudTable
    ref="table"
    :fetch-page="listServiceProviders"
    :delete-item="deleteServiceProvider"
    :headers="headers"
    :sort-by="[{ key: 'name', order: 'asc' }]"
    :search-placeholder="$t('serviceProviders.searchPlaceholder')"
    :filters="filters"
    filters-storage-key="service-providers"
    :empty-text="$t('serviceProviders.empty')"
    :no-results-text="$t('serviceProviders.noResults')"
    :delete-title="$t('serviceProviders.deleteTitle')"
    :delete-message="(p: ServiceProvider) => $t('serviceProviders.deleteConfirm', { name: p.name })"
    :deleted-text="$t('serviceProviders.deleted')"
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
    <template #[`filter.tax_id`]>
      <v-text-field
        v-model="typed.tax_id"
        :placeholder="$t('customers.fields.taxIdBrazil')"
        density="compact"
        hide-details
        clearable
        data-testid="filter-tax-id"
      />
    </template>
    <template #[`filter.services`]>
      <v-select
        v-model="filters.service"
        :items="serviceOptions"
        :placeholder="$t('common.filters.all')"
        density="compact"
        hide-details
        clearable
        data-testid="filter-service"
      />
    </template>
    <template #[`filter.city`]>
      <v-text-field
        v-model="typed.location"
        :placeholder="$t('serviceProviders.fields.location')"
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
    <template #[`item.name`]="{ item }">
      <div class="py-2">
        <div>{{ item.name }}</div>
        <div v-if="item.trade_name" class="text-caption text-medium-emphasis">
          {{ item.trade_name }}
        </div>
      </div>
    </template>
    <template #[`item.tax_id`]="{ item }">
      <span class="text-no-wrap">{{ formatTaxId(item.tax_id, item.country) }}</span>
    </template>
    <template #[`item.services`]="{ item }">
      <div class="d-flex flex-wrap ga-1 py-1" data-testid="services-cell">
        <v-chip
          v-for="kind in (item as ServiceProvider).services"
          :key="kind"
          :prepend-icon="SERVICE_ICONS[kind]"
          size="x-small"
          variant="tonal"
          label
        >
          {{ $t(`serviceProviders.services.${kind}`) }}
        </v-chip>
      </div>
    </template>
    <template #[`item.city`]="{ item }">{{ location(item) }}</template>
    <template #[`item.is_active`]="{ item }">
      <ActiveChip :active="item.is_active" />
    </template>
  </ServerCrudTable>

  <ServiceProviderFormDialog v-model="formOpen" :provider="editing" @saved="onSaved" />
</template>
