<script setup lang="ts">
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { deleteErrorMessage } from '@/api'
import ConfirmDialog from '@/components/ConfirmDialog.vue'
import { useServerTable } from '@/composables/useServerTable'
import { useNotificationsStore } from '@/stores/notifications'
import CustomerFormDialog from './CustomerFormDialog.vue'
import { deleteCustomer, listCustomers, type Customer } from './api'
import { formatTaxId } from './format'

const { t } = useI18n()
const notifications = useNotificationsStore()

// --- Grid (server-side pagination, sorting and search) ---------------------------------------

const {
  items,
  total,
  loading,
  loadError,
  page,
  itemsPerPage,
  sortBy,
  searchInput,
  search,
  load,
  reloadAfterDelete,
} = useServerTable(listCustomers, {
  sortBy: [{ key: 'name', order: 'asc' }],
  orderingFields: { account_manager_name: 'account_manager__full_name' },
})

const headers = computed(() => [
  { title: t('customers.fields.id'), key: 'id', width: 90 },
  { title: t('customers.fields.name'), key: 'name' },
  { title: t('customers.fields.taxId'), key: 'tax_id', width: 200 },
  { title: t('customers.fields.location'), key: 'city' },
  { title: t('customers.fields.accountManager'), key: 'account_manager_name' },
  { title: t('customers.fields.status'), key: 'is_active', width: 120 },
  {
    title: t('common.actions'),
    key: 'actions',
    sortable: false,
    align: 'end' as const,
    width: 120,
  },
])

function location(c: Customer): string {
  return [c.city, c.state].filter(Boolean).join(' / ')
}

// --- Create / edit ---------------------------------------------------------------------------

const formOpen = ref(false)
const editing = ref<Customer | null>(null)

function openCreate() {
  editing.value = null
  formOpen.value = true
}

function openEdit(customer: Customer) {
  editing.value = customer
  formOpen.value = true
}

function onSaved(_customer: Customer, created: boolean) {
  notifications.notify(t(created ? 'customers.created' : 'customers.updated'))
  load()
}

// --- Delete ----------------------------------------------------------------------------------

const deleting = ref<Customer | null>(null)
const confirmOpen = ref(false)
const deleteInProgress = ref(false)

function askDelete(customer: Customer) {
  deleting.value = customer
  confirmOpen.value = true
}

async function confirmDelete() {
  if (!deleting.value) return
  deleteInProgress.value = true
  try {
    await deleteCustomer(deleting.value.id)
    notifications.notify(t('customers.deleted'))
    confirmOpen.value = false
    await reloadAfterDelete()
  } catch (error) {
    notifications.notify(deleteErrorMessage(error, t('common.deleteError')), 'error')
    confirmOpen.value = false
  } finally {
    deleteInProgress.value = false
  }
}
</script>

<template>
  <v-container fluid style="max-width: 1400px">
    <div class="d-flex flex-wrap align-center ga-3 mb-4">
      <h1 class="text-h5 mr-auto">{{ $t('customers.title') }}</h1>
      <v-text-field
        v-model="searchInput"
        :placeholder="$t('customers.searchPlaceholder')"
        :aria-label="$t('common.search')"
        prepend-inner-icon="mdi-magnify"
        density="compact"
        clearable
        hide-details
        style="min-width: 260px; max-width: 400px"
        data-testid="search"
      />
      <v-btn color="primary" prepend-icon="mdi-plus" data-testid="new" @click="openCreate">
        {{ $t('common.new') }}
      </v-btn>
    </div>

    <v-alert v-if="loadError" type="error" variant="tonal" class="mb-4">
      {{ $t('common.loadError') }}
      <template #append>
        <v-btn variant="text" size="small" @click="load">{{ $t('common.retry') }}</v-btn>
      </template>
    </v-alert>

    <v-card>
      <v-data-table-server
        v-model:page="page"
        v-model:items-per-page="itemsPerPage"
        v-model:sort-by="sortBy"
        :headers="headers"
        :items="items"
        :items-length="total"
        :loading="loading"
        :search="search"
        :items-per-page-options="[10, 25, 50, 100]"
        :no-data-text="search ? $t('customers.noResults') : $t('customers.empty')"
        must-sort
        hover
        @update:options="load"
      >
        <template #[`item.name`]="{ item }">
          <div>{{ item.name }}</div>
          <div v-if="item.trade_name" class="text-caption text-medium-emphasis">
            {{ item.trade_name }}
          </div>
        </template>
        <template #[`item.tax_id`]="{ item }">
          <span class="text-no-wrap">{{ formatTaxId(item.tax_id, item.country) }}</span>
        </template>
        <template #[`item.city`]="{ item }">{{ location(item) }}</template>
        <template #[`item.account_manager_name`]="{ item }">
          <span v-if="item.account_manager_name">{{ item.account_manager_name }}</span>
          <span v-else class="text-medium-emphasis">—</span>
        </template>
        <template #[`item.is_active`]="{ item }">
          <v-chip
            :color="item.is_active ? 'success' : undefined"
            size="small"
            variant="tonal"
            label
          >
            {{ item.is_active ? $t('customers.status.active') : $t('customers.status.inactive') }}
          </v-chip>
        </template>
        <template #[`item.actions`]="{ item }">
          <v-btn
            icon="mdi-pencil-outline"
            variant="text"
            size="small"
            :aria-label="$t('common.edit')"
            :title="$t('common.edit')"
            data-testid="edit"
            @click="openEdit(item)"
          />
          <v-btn
            icon="mdi-delete-outline"
            variant="text"
            size="small"
            color="error"
            :aria-label="$t('common.delete')"
            :title="$t('common.delete')"
            data-testid="delete"
            @click="askDelete(item)"
          />
        </template>
      </v-data-table-server>
    </v-card>

    <CustomerFormDialog v-model="formOpen" :customer="editing" @saved="onSaved" />

    <ConfirmDialog
      v-model="confirmOpen"
      :title="$t('customers.deleteTitle')"
      :message="$t('customers.deleteConfirm', { name: deleting?.name ?? '' })"
      :confirm-text="$t('common.delete')"
      :loading="deleteInProgress"
      @confirm="confirmDelete"
    />
  </v-container>
</template>
