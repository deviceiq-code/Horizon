<script setup lang="ts">
/** The penalty table: a value per asset class and kind of finding, valid in a period (one
 * table for every customer; periods of the same class and kind never overlap). */
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import ServerCrudTable from '@/components/ServerCrudTable.vue'
import { useColumnFilters } from '@/composables/useColumnFilters'
import { useDateFormat } from '@/composables/useDateFormat'
import { useNotificationsStore } from '@/stores/notifications'
import { formatMoney } from '@/utils/money'
import PenaltyRateFormDialog from './PenaltyRateFormDialog.vue'
import { FINDING_KINDS, deletePenaltyRate, listPenaltyRates, type PenaltyRate } from './api'
import { useInventoryRoles } from './roles'

const { t, locale } = useI18n()
const { d } = useDateFormat()
const notifications = useNotificationsStore()
const { isSupervisor } = useInventoryRoles()

const table = ref<{ reload: () => Promise<void> } | null>(null)
const { filters, clear: clearFilters } = useColumnFilters(['finding_kind', 'current'] as const, [])
const kindOptions = computed(() =>
  FINDING_KINDS.map((value) => ({ value, title: t(`inventory.findings.kinds.${value}`) })),
)
const headers = computed(() => [
  { title: t('inventory.fields.assetClass'), key: 'asset_class__name' },
  { title: t('inventory.penalties.kind'), key: 'finding_kind' },
  { title: t('inventory.penalties.value'), key: 'value', width: 160 },
  { title: t('inventory.penalties.validity'), key: 'valid_from', width: 260 },
])

const formOpen = ref(false)
const editing = ref<PenaltyRate | null>(null)

function openForm(rate: PenaltyRate | null) {
  editing.value = rate
  formOpen.value = true
}

function onSaved(_rate: PenaltyRate, created: boolean) {
  notifications.notify(t(created ? 'inventory.penalties.created' : 'inventory.penalties.updated'))
  table.value?.reload()
}

const day = (value: string) => d(new Date(`${value}T12:00`), 'short')
</script>

<template>
  <ServerCrudTable
    ref="table"
    :fetch-page="listPenaltyRates"
    :delete-item="deletePenaltyRate"
    :headers="headers"
    :sort-by="[{ key: 'asset_class__name', order: 'asc' }]"
    :search-placeholder="$t('inventory.penalties.searchPlaceholder')"
    :filters="filters"
    filters-storage-key="inventory-penalties"
    :empty-text="$t('inventory.penalties.empty')"
    :no-results-text="$t('inventory.penalties.noResults')"
    :delete-title="$t('inventory.penalties.deleteTitle')"
    :delete-message="() => $t('inventory.penalties.deleteConfirm')"
    :deleted-text="$t('inventory.penalties.deleted')"
    :hide-create="!isSupervisor"
    :can-edit="() => isSupervisor"
    :can-delete="() => isSupervisor"
    @clear-filters="clearFilters"
    @create="openForm(null)"
    @edit="openForm"
  >
    <template #[`filter.finding_kind`]>
      <v-select
        v-model="filters.finding_kind"
        :items="kindOptions"
        :placeholder="$t('common.filters.all')"
        density="compact"
        hide-details
        clearable
      />
    </template>
    <template #[`filter.valid_from`]>
      <v-select
        v-model="filters.current"
        :items="[{ value: 'true', title: $t('inventory.penalties.validToday') }]"
        :placeholder="$t('common.filters.all')"
        density="compact"
        hide-details
        clearable
      />
    </template>
    <template #[`item.asset_class__name`]="{ item }">{{ item.asset_class_name }}</template>
    <template #[`item.finding_kind`]="{ item }">
      {{ $t(`inventory.findings.kinds.${item.finding_kind}`) }}
    </template>
    <template #[`item.value`]="{ item }">
      <span class="font-weight-medium">{{ formatMoney(item.value, 'BRL', locale) }}</span>
    </template>
    <template #[`item.valid_from`]="{ item }">
      {{ day(item.valid_from) }} –
      {{ item.valid_to ? day(item.valid_to) : $t('inventory.penalties.openEnded') }}
    </template>
  </ServerCrudTable>

  <PenaltyRateFormDialog v-model="formOpen" :rate="editing" @saved="onSaved" />
</template>
