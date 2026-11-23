<script setup lang="ts">
/** Business verticals (Administration › Catalogs): grid with column filters and rows that expand
 * to their sub-verticals, as Asset Classes'. */
import { computed, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import ServerCrudTable from '@/components/ServerCrudTable.vue'
import { useColumnFilters } from '@/composables/useColumnFilters'
import { listAccountManagers, type AccountManagerRef } from '@/modules/account-managers/api'
import { useNotificationsStore } from '@/stores/notifications'
import EnabledChip from '../EnabledChip.vue'
import RiskChip from './RiskChip.vue'
import VerticalFormDialog from './VerticalFormDialog.vue'
import { deleteVertical, listVerticals, type Vertical } from './api'

/** How many account manager chips to show per row before "+N". */
const MAX_CHIPS = 3

const { t } = useI18n()
const notifications = useNotificationsStore()

const table = ref<{ reload: () => Promise<void> } | null>(null)

// --- Column filters --------------------------------------------------------------------------

const {
  filters,
  typed,
  clear: clearFilters,
} = useColumnFilters(['name', 'account_manager', 'is_enabled'] as const, ['name'] as const)
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
  { value: 'true', title: t('catalogs.status.enabled') },
  { value: 'false', title: t('catalogs.status.disabled') },
])

const headers = computed(() => [
  { title: t('verticals.fields.id'), key: 'id', width: 80 },
  { title: t('verticals.fields.name'), key: 'name', minWidth: '240px' },
  { title: t('verticals.subVerticals'), key: 'sub_verticals', sortable: false, width: 160 },
  {
    title: t('verticals.fields.accountManagers'),
    key: 'account_managers_detail',
    sortable: false,
  },
  { title: t('verticals.fields.status'), key: 'is_enabled', width: 150 },
])

// --- Create / edit ---------------------------------------------------------------------------

const formOpen = ref(false)
const editing = ref<Vertical | null>(null)

function openForm(vertical: Vertical | null) {
  editing.value = vertical
  formOpen.value = true
}

function onSaved(_vertical: Vertical, created: boolean) {
  notifications.notify(t(created ? 'verticals.created' : 'verticals.updated'))
  table.value?.reload()
}
</script>

<template>
  <ServerCrudTable
    ref="table"
    :fetch-page="listVerticals"
    :delete-item="deleteVertical"
    :headers="headers"
    :sort-by="[{ key: 'name', order: 'asc' }]"
    :search-placeholder="$t('verticals.searchPlaceholder')"
    :filters="filters"
    filters-storage-key="verticals"
    :expandable="() => true"
    :empty-text="$t('verticals.empty')"
    :no-results-text="$t('verticals.noResults')"
    :delete-title="$t('verticals.deleteTitle')"
    :delete-message="(v: Vertical) => $t('verticals.deleteConfirm', { name: v.name })"
    :deleted-text="$t('verticals.deleted')"
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
    <template #[`filter.account_managers_detail`]>
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
    <template #[`item.sub_verticals`]="{ item }">
      {{ $t('verticals.subVerticalCount', item.sub_verticals.length) }}
    </template>
    <template #expanded-row="{ item }">
      <v-table density="compact" class="bg-transparent" data-testid="sub-verticals-table">
        <thead>
          <tr>
            <th class="pl-16">{{ $t('verticals.fields.subVertical') }}</th>
            <th>{{ $t('verticals.fields.risk') }}</th>
            <th>{{ $t('verticals.fields.allowedTerms') }}</th>
            <th>{{ $t('verticals.fields.recommendedTerm') }}</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="sub in item.sub_verticals" :key="sub.id" data-testid="sub-vertical-row">
            <td class="pl-16">
              <span v-if="sub.is_general" class="font-weight-medium">
                {{ $t('verticals.general') }}
              </span>
              <span v-else>{{ sub.name }}</span>
            </td>
            <td><RiskChip :risk="sub.risk" /></td>
            <td>{{ sub.allowed_terms.join(' · ') }}</td>
            <td class="font-weight-medium">
              {{ $t('verticals.months', sub.recommended_term ?? 0) }}
            </td>
          </tr>
        </tbody>
      </v-table>
    </template>
    <template #[`item.name`]="{ item }">
      <div class="py-2">
        <div>{{ item.name }}</div>
        <div
          v-if="item.notes"
          class="text-caption text-medium-emphasis text-truncate"
          style="max-width: 360px"
          :title="item.notes"
        >
          {{ item.notes }}
        </div>
      </div>
    </template>
    <template #[`item.account_managers_detail`]="{ item }">
      <div class="d-flex flex-wrap ga-1 py-1">
        <v-chip
          v-for="manager in item.account_managers_detail.slice(0, MAX_CHIPS)"
          :key="manager.id"
          size="small"
        >
          {{ manager.full_name }}
        </v-chip>
        <v-chip
          v-if="item.account_managers_detail.length > MAX_CHIPS"
          size="small"
          variant="text"
          :title="
            item.account_managers_detail
              .slice(MAX_CHIPS)
              .map((m: AccountManagerRef) => m.full_name)
              .join(', ')
          "
        >
          +{{ item.account_managers_detail.length - MAX_CHIPS }}
        </v-chip>
        <span v-if="!item.account_managers_detail.length" class="text-medium-emphasis"> — </span>
      </div>
    </template>
    <template #[`item.is_enabled`]="{ item }">
      <EnabledChip :enabled="item.is_enabled" />
    </template>
  </ServerCrudTable>

  <VerticalFormDialog v-model="formOpen" :vertical="editing" @saved="onSaved" />
</template>
