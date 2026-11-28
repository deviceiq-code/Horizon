<script setup lang="ts">
/** Disposals: the way out of the stock (relocations, sales, discards, parts). Commercial,
 * analysts and supervisors create them here; each continues on its own page. */
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'
import ServerCrudTable from '@/components/ServerCrudTable.vue'
import { useColumnFilters } from '@/composables/useColumnFilters'
import { useDateFormat } from '@/composables/useDateFormat'
import DisposalFormDialog from './DisposalFormDialog.vue'
import DisposalStatusChip from './DisposalStatusChip.vue'
import { DISPOSAL_KINDS, DISPOSAL_STATUSES, listDisposals, type Disposal } from './api'
import { useInventoryRoles } from './roles'

const { t } = useI18n()
const { d } = useDateFormat()
const router = useRouter()
const { canDispose } = useInventoryRoles()

const { filters, clear: clearFilters } = useColumnFilters(['status', 'kind'] as const, [])
const statusOptions = computed(() => [
  { value: 'open', title: t('inventory.disposals.openOnes') },
  ...DISPOSAL_STATUSES.map((value) => ({
    value,
    title: t(`inventory.disposals.statuses.${value}`),
  })),
])
const kindOptions = computed(() =>
  [...DISPOSAL_KINDS, 'parts' as const].map((value) => ({
    value,
    title: t(`inventory.disposals.kinds.${value}`),
  })),
)
const headers = computed(() => [
  { title: t('inventory.disposals.code'), key: 'code', sortable: false, width: 160 },
  { title: t('inventory.disposals.kind'), key: 'kind', width: 190 },
  { title: t('inventory.disposals.destination'), key: 'customer_name', sortable: false },
  { title: t('inventory.fields.warehouse'), key: 'warehouse', sortable: false, width: 110 },
  { title: t('inventory.disposals.items'), key: 'items_count', sortable: false, width: 130 },
  { title: t('inventory.disposals.createdAt'), key: 'created_at', width: 190 },
  { title: t('inventory.fields.status'), key: 'status', width: 140 },
])

const formOpen = ref(false)

function show(disposal: { id: number }) {
  router.push({ name: 'inventory-disposal', params: { id: disposal.id } })
}

const destination = (item: Disposal) =>
  item.customer_name ?? item.buyer_name ?? item.discard_provider_name ?? '—'
</script>

<template>
  <v-container fluid class="module-page">
    <h1 class="mb-1">{{ $t('inventory.disposals.title') }}</h1>
    <p class="text-medium-emphasis mb-4">{{ $t('inventory.disposals.subtitle') }}</p>

    <ServerCrudTable
      :fetch-page="listDisposals"
      :delete-item="async () => undefined"
      :headers="headers"
      :sort-by="[{ key: 'created_at', order: 'desc' }]"
      :search-placeholder="$t('inventory.disposals.searchPlaceholder')"
      :filters="filters"
      filters-storage-key="inventory-disposals"
      :empty-text="$t('inventory.disposals.empty')"
      :no-results-text="$t('inventory.disposals.noResults')"
      delete-title=""
      :delete-message="() => ''"
      deleted-text=""
      :hide-create="!canDispose"
      :can-delete="() => false"
      edit-icon="mdi-open-in-new"
      :edit-title="$t('inventory.disposals.show')"
      @clear-filters="clearFilters"
      @create="formOpen = true"
      @edit="show"
    >
      <template #[`filter.status`]>
        <v-select
          v-model="filters.status"
          :items="statusOptions"
          :placeholder="$t('common.filters.all')"
          density="compact"
          hide-details
          clearable
        />
      </template>
      <template #[`filter.kind`]>
        <v-select
          v-model="filters.kind"
          :items="kindOptions"
          :placeholder="$t('common.filters.all')"
          density="compact"
          hide-details
          clearable
        />
      </template>
      <template #[`item.code`]="{ item }">
        <div class="py-2">
          <div class="font-weight-medium">{{ item.code }}</div>
          <div v-if="item.document_number" class="text-caption text-medium-emphasis">
            {{ item.document_number }}
          </div>
        </div>
      </template>
      <template #[`item.kind`]="{ item }">{{
        $t(`inventory.disposals.kinds.${item.kind}`)
      }}</template>
      <template #[`item.customer_name`]="{ item }">
        <div>{{ destination(item) }}</div>
        <div v-if="item.contract" class="text-caption text-medium-emphasis">
          {{ $t('inventory.disposals.contract') }}: {{ item.contract }}
        </div>
      </template>
      <template #[`item.warehouse`]="{ item }">
        <span :title="item.warehouse_name">{{ item.warehouse_code }}</span>
      </template>
      <template #[`item.items_count`]="{ item }">
        {{
          $t('inventory.disposals.pickedOf', {
            picked: item.picked_count ?? 0,
            total: item.items_count ?? 0,
          })
        }}
      </template>
      <template #[`item.created_at`]="{ item }">{{
        d(new Date(item.created_at), 'dateTime')
      }}</template>
      <template #[`item.status`]="{ item }"><DisposalStatusChip :status="item.status" /></template>
    </ServerCrudTable>

    <DisposalFormDialog v-model="formOpen" :disposal="null" @saved="show" />
  </v-container>
</template>
