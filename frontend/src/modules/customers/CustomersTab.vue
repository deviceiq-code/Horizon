<script setup lang="ts">
/** Customers (Administration › Catalogs): grid with column filters, as Asset Classes'. */
import { computed, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import ActiveChip from '@/components/ActiveChip.vue'
import ServerCrudTable from '@/components/ServerCrudTable.vue'
import { useColumnFilters } from '@/composables/useColumnFilters'
import { listAccountManagers, type AccountManagerRef } from '@/modules/account-managers/api'
import { useNotificationsStore } from '@/stores/notifications'
import CustomerFormDialog from './CustomerFormDialog.vue'
import { deleteCustomer, listCustomers, type Customer } from './api'
import { formatTaxId } from './format'

const { t } = useI18n()
const notifications = useNotificationsStore()

const table = ref<{ reload: () => Promise<void> } | null>(null)

// --- Column filters --------------------------------------------------------------------------

const {
  filters,
  typed,
  clear: clearFilters,
} = useColumnFilters(
  ['name', 'tax_id', 'location', 'account_manager', 'is_active'] as const,
  ['name', 'tax_id', 'location'] as const,
)
const managers = ref<AccountManagerRef[]>([])
onMounted(async () => {
  try {
    const page = await listAccountManagers({ page: 1, pageSize: 200, ordering: 'first_name' })
    managers.value = page.results
  } catch {
    // The grid works without this filter's options
  }
})
const statusOptions = computed(() => [
  { value: 'true', title: t('customers.status.active') },
  { value: 'false', title: t('customers.status.inactive') },
])

const headers = computed(() => [
  { title: t('customers.fields.id'), key: 'id', width: 80 },
  { title: t('customers.fields.name'), key: 'name', minWidth: '240px' },
  { title: t('customers.fields.taxId'), key: 'tax_id', width: 200 },
  { title: t('customers.fields.location'), key: 'city', width: 200 },
  // Sorted by the primary account manager
  { title: t('customers.fields.accountManagers'), key: 'primary_account_manager_name' },
  { title: t('customers.fields.status'), key: 'is_active', width: 150 },
])

function location(c: Customer): string {
  return [c.city, c.state].filter(Boolean).join(' / ')
}

// --- Create / edit ---------------------------------------------------------------------------

const formOpen = ref(false)
const editing = ref<Customer | null>(null)

function openForm(customer: Customer | null) {
  editing.value = customer
  formOpen.value = true
}

function onSaved(_customer: Customer, created: boolean) {
  notifications.notify(t(created ? 'customers.created' : 'customers.updated'))
  table.value?.reload()
}
</script>

<template>
  <ServerCrudTable
    ref="table"
    :fetch-page="listCustomers"
    :delete-item="deleteCustomer"
    :headers="headers"
    :sort-by="[{ key: 'name', order: 'asc' }]"
    :ordering-fields="{ primary_account_manager_name: 'primary_account_manager__first_name' }"
    :search-placeholder="$t('customers.searchPlaceholder')"
    :filters="filters"
    filters-storage-key="customers"
    :empty-text="$t('customers.empty')"
    :no-results-text="$t('customers.noResults')"
    :delete-title="$t('customers.deleteTitle')"
    :delete-message="(c: Customer) => $t('customers.deleteConfirm', { name: c.name })"
    :deleted-text="$t('customers.deleted')"
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
    <template #[`filter.primary_account_manager_name`]>
      <v-autocomplete
        v-model="filters.account_manager"
        :items="managers"
        item-title="full_name"
        item-value="id"
        :placeholder="$t('common.filters.all')"
        density="compact"
        hide-details
        clearable
        data-testid="filter-account-manager"
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
    <template #[`item.city`]="{ item }">{{ location(item) }}</template>
    <template #[`item.primary_account_manager_name`]="{ item }">
      <div class="d-flex flex-wrap align-center ga-1 py-1">
        <span
          class="d-inline-flex align-center font-weight-medium text-no-wrap"
          :title="$t('customers.fields.primaryAccountManager')"
        >
          <v-icon icon="mdi-star" size="x-small" color="amber-darken-2" class="mr-1" />
          {{ item.primary_account_manager_name }}
        </span>
        <v-chip
          v-if="item.secondary_account_managers_detail.length"
          size="x-small"
          variant="tonal"
          :title="
            item.secondary_account_managers_detail
              .map((m: AccountManagerRef) => m.full_name)
              .join(', ')
          "
          data-testid="secondary-count"
        >
          +{{ item.secondary_account_managers_detail.length }}
        </v-chip>
      </div>
    </template>
    <template #[`item.is_active`]="{ item }">
      <ActiveChip :active="item.is_active" />
    </template>
  </ServerCrudTable>

  <CustomerFormDialog v-model="formOpen" :customer="editing" @saved="onSaved" />
</template>
