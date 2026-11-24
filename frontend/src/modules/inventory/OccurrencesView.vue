<script setup lang="ts">
/**
 * Every occurrence in one place: from receiving lots, transfers, inventory counts and those
 * found while moving (location divergence — RN-19). Receivers and supervisors resolve them;
 * only supervisors accept a divergence as it is.
 */
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { ApiError } from '@/api'
import ServerCrudTable from '@/components/ServerCrudTable.vue'
import { useColumnFilters } from '@/composables/useColumnFilters'
import { useDateFormat } from '@/composables/useDateFormat'
import { useNotificationsStore } from '@/stores/notifications'
import {
  OCCURRENCE_KINDS,
  acceptOccurrence,
  listOccurrences,
  resolveOccurrence,
  type Occurrence,
} from './api'
import { useInventoryRoles } from './roles'

const { t } = useI18n()
const { d } = useDateFormat()
const notifications = useNotificationsStore()
const { canReceive, isSupervisor } = useInventoryRoles()
const table = ref<{ reload: () => Promise<void> } | null>(null)

const { filters, clear: clearFilters } = useColumnFilters(['source', 'kind', 'status'] as const, [])
const sourceOptions = computed(() =>
  (['lot', 'transfer', 'count', 'movement'] as const).map((value) => ({
    value,
    title: t(`inventory.occurrencesPage.sources.${value}`),
  })),
)
const kindOptions = computed(() =>
  OCCURRENCE_KINDS.map((value) => ({ value, title: t(`inventory.occurrences.kinds.${value}`) })),
)
const statusOptions = computed(() =>
  (['open', 'resolved', 'accepted'] as const).map((value) => ({
    value,
    title: t(`inventory.occurrences.statuses.${value}`),
  })),
)
const headers = computed(() => [
  { title: t('inventory.occurrencesPage.source'), key: 'source', sortable: false, width: 180 },
  { title: t('inventory.occurrences.kind'), key: 'kind', sortable: false, width: 200 },
  { title: t('inventory.fields.asset'), key: 'asset', sortable: false },
  { title: t('inventory.fields.status'), key: 'status', sortable: false, width: 150 },
  {
    title: t('inventory.occurrencesPage.createdAt'),
    key: 'created_at',
    sortable: false,
    width: 180,
  },
])

function source(o: Occurrence) {
  if (o.lot_code) return o.lot_code
  if (o.transfer_code) return o.transfer_code
  if (o.count_code) return o.count_code
  return t('inventory.occurrencesPage.sources.movement')
}

const open = ref(false)
const current = ref<Occurrence | null>(null)
const accepting = ref(false)
const resolution = ref('')
function openDialog(o: Occurrence, accept: boolean) {
  current.value = o
  accepting.value = accept
  resolution.value = ''
  open.value = true
}
async function save() {
  if (!current.value) return
  try {
    await (accepting.value ? acceptOccurrence : resolveOccurrence)(
      current.value.id,
      resolution.value,
    )
    open.value = false
    await table.value?.reload()
  } catch (error) {
    notifications.notify(error instanceof ApiError ? error.message : t('common.saveError'), 'error')
  }
}
</script>

<template>
  <v-container fluid class="module-page">
    <h1 class="mb-1">{{ $t('inventory.occurrencesPage.title') }}</h1>
    <p class="text-medium-emphasis mb-4">{{ $t('inventory.occurrencesPage.subtitle') }}</p>

    <ServerCrudTable
      ref="table"
      :fetch-page="listOccurrences"
      :delete-item="async () => undefined"
      :headers="headers"
      :sort-by="[{ key: 'created_at', order: 'desc' }]"
      :search-placeholder="$t('inventory.occurrencesPage.searchPlaceholder')"
      :filters="filters"
      filters-storage-key="inventory-occurrences"
      :empty-text="$t('inventory.occurrences.empty')"
      :no-results-text="$t('inventory.occurrencesPage.noResults')"
      delete-title=""
      :delete-message="() => ''"
      deleted-text=""
      hide-create
      :can-edit="() => false"
      :can-delete="() => false"
      @clear-filters="clearFilters"
    >
      <template #[`filter.source`]>
        <v-select
          v-model="filters.source"
          :items="sourceOptions"
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
      <template #[`item.source`]="{ item }">{{ source(item) }}</template>
      <template #[`item.kind`]="{ item }">{{
        $t(`inventory.occurrences.kinds.${item.kind}`)
      }}</template>
      <template #[`item.asset`]="{ item }">
        <div class="py-2">
          <div class="font-weight-medium">
            {{ item.asset_code ?? item.asset_model_label ?? '—' }}
            <span v-if="!item.asset_code && item.quantity > 1"> × {{ item.quantity }}</span>
          </div>
          <div v-if="item.description" class="text-caption text-medium-emphasis">
            {{ item.description }}
          </div>
          <div v-if="item.resolution" class="text-caption">
            {{ item.resolution }} — {{ item.resolved_by_name }}
          </div>
        </div>
      </template>
      <template #[`item.status`]="{ item }">
        <v-chip
          :color="item.status === 'open' ? 'warning' : 'success'"
          size="small"
          variant="tonal"
          label
          >{{ $t(`inventory.occurrences.statuses.${item.status}`) }}</v-chip
        >
      </template>
      <template #[`item.created_at`]="{ item }">{{
        d(new Date(item.created_at), 'dateTime')
      }}</template>
      <template #row-actions="{ item }">
        <template v-if="item.status === 'open'">
          <v-btn
            v-if="canReceive"
            size="small"
            variant="tonal"
            class="mr-1"
            @click="openDialog(item, false)"
            >{{ $t('inventory.occurrences.resolve') }}</v-btn
          >
          <v-btn v-if="isSupervisor" size="small" variant="tonal" @click="openDialog(item, true)">{{
            $t('inventory.occurrences.accept')
          }}</v-btn>
        </template>
      </template>
    </ServerCrudTable>

    <v-dialog v-model="open" max-width="480">
      <v-card
        :title="
          accepting ? $t('inventory.occurrences.accept') : $t('inventory.occurrences.resolve')
        "
      >
        <v-card-text>
          <v-textarea
            v-model="resolution"
            :label="$t('inventory.transfers.resolution')"
            rows="2"
            auto-grow
          />
        </v-card-text>
        <v-card-actions>
          <v-spacer />
          <v-btn variant="text" @click="open = false">{{ $t('common.close') }}</v-btn>
          <v-btn color="primary" variant="flat" :disabled="!resolution.trim()" @click="save">{{
            $t('common.save')
          }}</v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>
  </v-container>
</template>
