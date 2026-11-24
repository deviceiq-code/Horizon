<script setup lang="ts">
/** Transfers between warehouses: analysts and supervisors request them here; each continues on
 * its own page (approval, picking, sending, receiving). */
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'
import ServerCrudTable from '@/components/ServerCrudTable.vue'
import { useColumnFilters } from '@/composables/useColumnFilters'
import { useDateFormat } from '@/composables/useDateFormat'
import TransferFormDialog from './TransferFormDialog.vue'
import TransferStatusChip from './TransferStatusChip.vue'
import { TRANSFER_STATUSES, listTransfers } from './api'
import { useInventoryRoles } from './roles'

const { t } = useI18n()
const { d } = useDateFormat()
const router = useRouter()
const { canRequestTransfer } = useInventoryRoles()

const { filters, clear: clearFilters } = useColumnFilters(['status'] as const, [])
const statusOptions = computed(() => [
  { value: 'open', title: t('inventory.transfers.openOnes') },
  ...TRANSFER_STATUSES.map((value) => ({
    value,
    title: t(`inventory.transfers.statuses.${value}`),
  })),
])
const headers = computed(() => [
  { title: t('inventory.transfers.code'), key: 'code', sortable: false, width: 160 },
  { title: t('inventory.transfers.route'), key: 'route', sortable: false, width: 170 },
  { title: t('inventory.transfers.reason'), key: 'reason', sortable: false },
  { title: t('inventory.transfers.items'), key: 'items_count', sortable: false, width: 150 },
  { title: t('inventory.transfers.requestedAt'), key: 'requested_at', width: 190 },
  { title: t('inventory.fields.status'), key: 'status', width: 230 },
])

const formOpen = ref(false)

function show(transfer: { id: number }) {
  router.push({ name: 'inventory-transfer', params: { id: transfer.id } })
}
</script>

<template>
  <v-container fluid class="module-page">
    <h1 class="mb-1">{{ $t('inventory.transfers.title') }}</h1>
    <p class="text-medium-emphasis mb-4">{{ $t('inventory.transfers.subtitle') }}</p>

    <ServerCrudTable
      :fetch-page="listTransfers"
      :delete-item="async () => undefined"
      :headers="headers"
      :sort-by="[{ key: 'requested_at', order: 'desc' }]"
      :search-placeholder="$t('inventory.transfers.searchPlaceholder')"
      :filters="filters"
      filters-storage-key="inventory-transfers"
      :empty-text="$t('inventory.transfers.empty')"
      :no-results-text="$t('inventory.transfers.noResults')"
      delete-title=""
      :delete-message="() => ''"
      deleted-text=""
      :hide-create="!canRequestTransfer"
      :can-delete="() => false"
      edit-icon="mdi-open-in-new"
      :edit-title="$t('inventory.transfers.show')"
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
      <template #[`item.code`]="{ item }">
        <div class="py-2">
          <div class="font-weight-medium">{{ item.code }}</div>
          <div v-if="item.fiscal_document_number" class="text-caption text-medium-emphasis">
            {{ item.fiscal_document_number }}
          </div>
        </div>
      </template>
      <template #[`item.route`]="{ item }">
        <span :title="`${item.origin_name} → ${item.destination_name}`"
          >{{ item.origin_code }} → {{ item.destination_code }}</span
        >
      </template>
      <template #[`item.items_count`]="{ item }">
        {{ $t('inventory.transfers.count', { n: item.items_count ?? 0 }) }}
      </template>
      <template #[`item.requested_at`]="{ item }">{{
        d(new Date(item.requested_at), 'dateTime')
      }}</template>
      <template #[`item.status`]="{ item }"
        ><TransferStatusChip :status="item.status" :days-late="item.days_late"
      /></template>
    </ServerCrudTable>

    <TransferFormDialog v-model="formOpen" :transfer="null" @saved="show" />
  </v-container>
</template>
