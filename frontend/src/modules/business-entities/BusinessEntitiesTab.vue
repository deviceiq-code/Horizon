<script setup lang="ts">
/**
 * Business Entities (Administration › Catalogs): a tab per role, then "All" — each one a grid
 * (as Asset Classes') with that role's columns and, in Status, that role's "active" (and the
 * entity's). An entity with several roles shows in each of their tabs. New in a role's tab
 * starts with that role. The tab open is in the address (?tab=customer).
 */
import { computed, onMounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute, useRouter } from 'vue-router'
import ActiveChip from '@/components/ActiveChip.vue'
import ServerCrudTable from '@/components/ServerCrudTable.vue'
import type { ListParams } from '@/api'
import { useColumnFilters } from '@/composables/useColumnFilters'
import { listAccountManagers, type AccountManagerRef } from '@/modules/account-managers/api'
import { formatTaxId } from '@/modules/customers/format'
import { SERVICE_ICONS, SERVICE_KINDS } from '@/modules/service-providers/api'
import { useNotificationsStore } from '@/stores/notifications'
import BusinessEntityFormDialog from './BusinessEntityFormDialog.vue'
import {
  CONTRACT_TYPES,
  deleteBusinessEntity,
  entityCounts,
  ENTITY_ROLES,
  listBusinessEntities,
  ROLE_ICONS,
  SUPPLY_KINDS,
  type BusinessEntity,
  type EntityCounts,
  type EntityRole,
} from './api'

type Tab = 'all' | EntityRole

const { t } = useI18n()
const route = useRoute()
const router = useRouter()
const notifications = useNotificationsStore()

const isTab = (value: unknown): value is Tab =>
  value === 'all' || ENTITY_ROLES.includes(value as EntityRole)
const tab = ref<Tab>(isTab(route.query.tab) ? route.query.tab : 'all')
const role = computed<EntityRole | null>(() => (tab.value === 'all' ? null : tab.value))

const table = ref<{ reload: () => Promise<void> } | null>(null)

// --- Counts per tab --------------------------------------------------------------------------

const counts = ref<EntityCounts | null>(null)
async function loadCounts() {
  try {
    counts.value = await entityCounts()
  } catch {
    // The tabs work without their counts
  }
}
onMounted(loadCounts)

// --- Column filters --------------------------------------------------------------------------

const {
  filters,
  typed,
  clear: clearFilters,
} = useColumnFilters(
  [
    'name',
    'tax_id',
    'location',
    'is_active',
    'contract_type',
    'account_manager',
    'service',
    'supplies',
  ] as const,
  ['name', 'tax_id', 'location'] as const,
)

watch(tab, (value) => {
  clearFilters()
  void router.replace({ query: { ...route.query, tab: value === 'all' ? undefined : value } })
})

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
const contractTypeOptions = computed(() =>
  CONTRACT_TYPES.map((kind) => ({
    value: kind,
    title: t(`businessEntities.contractTypes.${kind}`),
  })),
)
const serviceOptions = computed(() =>
  SERVICE_KINDS.map((kind) => ({ value: kind, title: t(`serviceProviders.services.${kind}`) })),
)
const supplyOptions = computed(() =>
  SUPPLY_KINDS.map((kind) => ({ value: kind, title: t(`businessEntities.supplies.${kind}`) })),
)

// --- The grid of the tab ---------------------------------------------------------------------

function fetchPage(params: ListParams) {
  return listBusinessEntities({
    ...params,
    filters: { ...params.filters, ...(role.value ? { role: role.value } : {}) },
  })
}

async function deleteEntity(id: number) {
  await deleteBusinessEntity(id)
  void loadCounts()
}

interface Column {
  title: string
  key: string
  width?: number
  minWidth?: string
  sortable?: boolean
}

const headers = computed(() => {
  const columns: Column[] = [
    { title: t('customers.fields.name'), key: 'name', minWidth: '240px' },
    { title: t('customers.fields.taxId'), key: 'tax_id', width: 190 },
  ]
  if (!role.value) {
    columns.push(
      {
        title: t('businessEntities.fields.roles'),
        key: 'roles',
        sortable: false,
        minWidth: '220px',
      },
      { title: t('businessEntities.fields.group'), key: 'parent', minWidth: '180px' },
    )
  } else if (role.value === 'customer') {
    columns.push(
      {
        title: t('businessEntities.fields.contractTypes'),
        key: 'contract_types',
        sortable: false,
      },
      { title: t('customers.fields.accountManagers'), key: 'account_managers' },
    )
  } else if (role.value === 'service_provider') {
    columns.push({
      title: t('serviceProviders.fields.services'),
      key: 'services',
      sortable: false,
    })
  } else if (role.value === 'supplier') {
    columns.push({
      title: t('businessEntities.fields.supplies'),
      key: 'supplies',
      sortable: false,
    })
  }
  columns.push(
    { title: t('customers.fields.location'), key: 'city', width: 190 },
    { title: t('customers.fields.status'), key: 'is_active', width: 130 },
  )
  return columns
})

function location(e: BusinessEntity): string {
  return [e.city, e.state].filter(Boolean).join(' / ')
}

/** In a role's tab, active in the role and as an entity */
function isActive(e: BusinessEntity): boolean {
  const current = role.value ? e[role.value] : null
  return role.value ? e.is_active && !!current?.is_active : e.is_active
}

// --- Create / edit ---------------------------------------------------------------------------

const formOpen = ref(false)
const editing = ref<BusinessEntity | null>(null)

function openForm(entity: BusinessEntity | null) {
  editing.value = entity
  formOpen.value = true
}

function onSaved(_entity: BusinessEntity, created: boolean) {
  notifications.notify(t(created ? 'businessEntities.created' : 'businessEntities.updated'))
  void table.value?.reload()
  void loadCounts()
}
</script>

<template>
  <v-tabs v-model="tab" color="primary" class="mb-4" show-arrows data-testid="entity-tabs">
    <v-tab
      v-for="r in ENTITY_ROLES"
      :key="r"
      :value="r"
      :prepend-icon="ROLE_ICONS[r]"
      :data-testid="`tab-${r}`"
    >
      {{ $t(`businessEntities.roles.${r}.many`) }}
      <v-chip v-if="counts" size="x-small" variant="tonal" class="ml-2">{{ counts[r] }}</v-chip>
    </v-tab>
    <!-- The last one: every entity -->
    <v-tab value="all" prepend-icon="mdi-domain" data-testid="tab-all">
      {{ $t('businessEntities.tabs.all') }}
      <v-chip v-if="counts" size="x-small" variant="tonal" class="ml-2">{{ counts.all }}</v-chip>
    </v-tab>
  </v-tabs>

  <ServerCrudTable
    :key="tab"
    ref="table"
    :fetch-page="fetchPage"
    :delete-item="deleteEntity"
    :headers="headers"
    :sort-by="[{ key: 'name', order: 'asc' }]"
    :ordering-fields="{
      parent: 'parent__name',
      account_managers: 'customer__primary_account_manager__first_name',
    }"
    :search-placeholder="$t('businessEntities.searchPlaceholder')"
    :filters="filters"
    filters-storage-key="business-entities"
    :empty-text="$t('businessEntities.empty')"
    :no-results-text="$t('businessEntities.noResults')"
    :delete-title="$t('businessEntities.deleteTitle')"
    :delete-message="
      (e: BusinessEntity) => $t('businessEntities.deleteConfirm', { name: e.trade_name || e.name })
    "
    :deleted-text="$t('businessEntities.deleted')"
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
    <template #[`filter.account_managers`]>
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
    <template #[`filter.contract_types`]>
      <v-select
        v-model="filters.contract_type"
        :items="contractTypeOptions"
        :placeholder="$t('common.filters.all')"
        density="compact"
        hide-details
        clearable
        data-testid="filter-contract-type"
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
    <template #[`filter.supplies`]>
      <v-select
        v-model="filters.supplies"
        :items="supplyOptions"
        :placeholder="$t('common.filters.all')"
        density="compact"
        hide-details
        clearable
        data-testid="filter-supplies"
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
        <div v-if="item.keywords.length" class="text-caption text-medium-emphasis">
          <v-icon icon="mdi-tag-outline" size="x-small" /> {{ item.keywords.join(', ') }}
        </div>
      </div>
    </template>
    <template #[`item.tax_id`]="{ item }">
      <span class="text-no-wrap">{{ formatTaxId(item.tax_id, item.country) }}</span>
    </template>
    <template #[`item.roles`]="{ item }">
      <div class="d-flex flex-wrap ga-1 py-1" data-testid="roles-cell">
        <v-chip
          v-for="r in item.roles"
          :key="r"
          size="x-small"
          :prepend-icon="ROLE_ICONS[r as EntityRole]"
          :variant="item[r as EntityRole]?.is_active ? 'tonal' : 'outlined'"
          :color="item[r as EntityRole]?.is_active ? 'primary' : undefined"
          :title="item[r as EntityRole]?.is_active ? undefined : $t('customers.status.inactive')"
        >
          {{ $t(`businessEntities.roles.${r}.one`) }}
        </v-chip>
      </div>
    </template>
    <template #[`item.parent`]="{ item }">
      <!-- Its head office, or the branches it heads -->
      <div v-if="item.parent_detail" class="text-body-2">
        <v-icon icon="mdi-source-branch" size="x-small" class="mr-1" />
        {{ item.parent_detail.trade_name || item.parent_detail.name }}
        <div
          v-if="item.group_detail && item.group_detail.id !== item.parent_detail.id"
          class="text-caption text-medium-emphasis"
        >
          {{
            $t('businessEntities.groupOf', {
              name: item.group_detail.trade_name || item.group_detail.name,
            })
          }}
        </div>
      </div>
      <span v-else-if="item.branches_count" class="text-body-2">
        <v-icon icon="mdi-office-building-outline" size="x-small" class="mr-1" />
        {{ $t('businessEntities.headOfBranches', item.branches_count) }}
      </span>
    </template>
    <template #[`item.account_managers`]="{ item }">
      <div v-if="item.customer" class="d-flex flex-wrap align-center ga-1 py-1">
        <span class="d-inline-flex align-center font-weight-medium text-no-wrap">
          <v-icon icon="mdi-star" size="x-small" color="amber-darken-2" class="mr-1" />
          {{ item.customer.primary_account_manager_name }}
        </span>
        <v-chip
          v-if="item.customer.secondary_account_managers_detail.length"
          size="x-small"
          variant="tonal"
          :title="
            item.customer.secondary_account_managers_detail
              .map((m: AccountManagerRef) => m.full_name)
              .join(', ')
          "
        >
          +{{ item.customer.secondary_account_managers_detail.length }}
        </v-chip>
      </div>
    </template>
    <template #[`item.contract_types`]="{ item }">
      <div class="d-flex flex-wrap ga-1 py-1" data-testid="contract-types-cell">
        <v-chip
          v-for="kind in (item as BusinessEntity).customer?.contract_types ?? []"
          :key="kind"
          size="x-small"
          variant="tonal"
        >
          {{ $t(`businessEntities.contractTypes.${kind}`) }}
        </v-chip>
      </div>
    </template>
    <template #[`item.services`]="{ item }">
      <div class="d-flex flex-wrap ga-1 py-1">
        <v-chip
          v-for="kind in (item as BusinessEntity).service_provider?.services ?? []"
          :key="kind"
          size="x-small"
          variant="tonal"
          :prepend-icon="SERVICE_ICONS[kind]"
        >
          {{ $t(`serviceProviders.services.${kind}`) }}
        </v-chip>
      </div>
    </template>
    <template #[`item.supplies`]="{ item }">
      <div class="d-flex flex-wrap ga-1 py-1">
        <v-chip
          v-for="kind in item.supplier?.supplies ?? []"
          :key="kind"
          size="x-small"
          variant="tonal"
        >
          {{ $t(`businessEntities.supplies.${kind}`) }}
        </v-chip>
      </div>
    </template>
    <template #[`item.city`]="{ item }">{{ location(item) }}</template>
    <template #[`item.is_active`]="{ item }">
      <ActiveChip :active="isActive(item)" />
    </template>
  </ServerCrudTable>

  <BusinessEntityFormDialog
    v-model="formOpen"
    :entity="editing"
    :start-role="role"
    @saved="onSaved"
  />
</template>
