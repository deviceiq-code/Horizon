<script setup lang="ts">
/** Receiving lots: open ones first; a receiver opens an unscheduled lot here (scheduled ones
 * start from their appointment) and continues the triage on the lot's page. */
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'
import ServerCrudTable from '@/components/ServerCrudTable.vue'
import { useColumnFilters } from '@/composables/useColumnFilters'
import { useDateFormat } from '@/composables/useDateFormat'
import LotOpenDialog from './LotOpenDialog.vue'
import LotStatusChip from './LotStatusChip.vue'
import { listLots, type Lot } from './api'
import { useInventoryRoles } from './roles'

const { t } = useI18n()
const { d } = useDateFormat()
const router = useRouter()
const { canReceive } = useInventoryRoles()

const { filters, clear: clearFilters } = useColumnFilters(['status'] as const, [])
const statusOptions = computed(() =>
  (['open', 'reconciling', 'closed'] as const).map((value) => ({
    value,
    title: t(`inventory.lots.statuses.${value}`),
  })),
)
const headers = computed(() => [
  { title: t('inventory.lots.code'), key: 'code', sortable: false, width: 150 },
  { title: t('inventory.appointments.customer'), key: 'customer_name', sortable: false },
  { title: t('inventory.fields.warehouse'), key: 'warehouse', sortable: false, width: 120 },
  { title: t('inventory.lots.units'), key: 'units_count', sortable: false, width: 110 },
  { title: t('inventory.lots.occurrences'), key: 'open_occurrences', sortable: false, width: 140 },
  { title: t('inventory.lots.openedAt'), key: 'opened_at', width: 200 },
  { title: t('inventory.fields.status'), key: 'status', width: 150 },
])

const openDialog = ref(false)

function show(lot: Lot) {
  router.push({ name: 'inventory-lot', params: { id: lot.id } })
}
</script>

<template>
  <v-container fluid class="module-page">
    <h1 class="mb-1">{{ $t('inventory.lots.title') }}</h1>
    <p class="text-medium-emphasis mb-4">{{ $t('inventory.lots.subtitle') }}</p>

    <ServerCrudTable
      :fetch-page="listLots"
      :delete-item="async () => undefined"
      :headers="headers"
      :sort-by="[{ key: 'opened_at', order: 'desc' }]"
      :search-placeholder="$t('inventory.lots.searchPlaceholder')"
      :filters="filters"
      filters-storage-key="inventory-lots"
      :empty-text="$t('inventory.lots.empty')"
      :no-results-text="$t('inventory.lots.noResults')"
      delete-title=""
      :delete-message="() => ''"
      deleted-text=""
      :hide-create="!canReceive"
      :can-delete="() => false"
      edit-icon="mdi-open-in-new"
      :edit-title="$t('inventory.lots.show')"
      @clear-filters="clearFilters"
      @create="openDialog = true"
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
          <div class="text-caption text-medium-emphasis">
            {{ item.appointment_detail?.code ?? $t('inventory.lots.unscheduled') }}
          </div>
        </div>
      </template>
      <template #[`item.warehouse`]="{ item }">
        <span :title="item.warehouse_detail.name">{{ item.warehouse_detail.code }}</span>
      </template>
      <template #[`item.open_occurrences`]="{ item }">
        <v-chip v-if="item.open_occurrences" color="warning" size="small" variant="tonal" label>
          {{ $t('inventory.lots.openCount', item.open_occurrences) }}
        </v-chip>
        <span v-else class="text-medium-emphasis">—</span>
      </template>
      <template #[`item.opened_at`]="{ item }">{{
        d(new Date(item.opened_at), 'dateTime')
      }}</template>
      <template #[`item.status`]="{ item }"><LotStatusChip :status="item.status" /></template>
    </ServerCrudTable>

    <LotOpenDialog v-model="openDialog" :appointment="null" @opened="show" />
  </v-container>
</template>
