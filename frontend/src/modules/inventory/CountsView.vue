<script setup lang="ts">
/** Inventory counts: supervisors open them here (cyclic: some locations and everything under
 * them; general: the whole warehouse); each continues on its own page. */
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'
import { ApiError } from '@/api'
import FormDialog from '@/components/FormDialog.vue'
import ServerCrudTable from '@/components/ServerCrudTable.vue'
import { useColumnFilters } from '@/composables/useColumnFilters'
import { useDateFormat } from '@/composables/useDateFormat'
import { listWarehouses, type Warehouse } from '@/modules/warehouses/api'
import CountStatusChip from './CountStatusChip.vue'
import {
  COUNT_STATUSES,
  listCounts,
  listLocations,
  openCount,
  type CountKind,
  type Location,
} from './api'
import { useInventoryRoles } from './roles'

const { t } = useI18n()
const { d } = useDateFormat()
const router = useRouter()
const { isSupervisor } = useInventoryRoles()

const { filters, clear: clearFilters } = useColumnFilters(['status'] as const, [])
const statusOptions = computed(() =>
  COUNT_STATUSES.map((value) => ({ value, title: t(`inventory.counts.statuses.${value}`) })),
)
const headers = computed(() => [
  { title: t('inventory.counts.code'), key: 'code', sortable: false, width: 160 },
  { title: t('inventory.fields.warehouse'), key: 'warehouse', sortable: false, width: 120 },
  { title: t('inventory.counts.kind'), key: 'kind', sortable: false, width: 130 },
  { title: t('inventory.counts.scope'), key: 'locations_count', sortable: false },
  { title: t('inventory.counts.accuracy'), key: 'accuracy', sortable: false, width: 150 },
  { title: t('inventory.counts.createdAt'), key: 'created_at', width: 190 },
  { title: t('inventory.fields.status'), key: 'status', width: 150 },
])

function show(count: { id: number }) {
  router.push({ name: 'inventory-count', params: { id: count.id } })
}

// --- Opening -----------------------------------------------------------------------------------

const formOpen = ref(false)
const warehouses = ref<Warehouse[]>([])
const warehouse = ref<number | null>(null)
const kind = ref<CountKind>('cyclic')
const locations = ref<Location[]>([])
const chosen = ref<number[]>([])
const notes = ref('')
const error = ref('')
const saving = ref(false)
const formRef = ref<{ validate: () => Promise<{ valid: boolean }> } | null>(null)

const warehouseOptions = computed(() =>
  warehouses.value.map((w) => ({ value: w.id, title: `${w.code} · ${w.name}` })),
)
const locationOptions = computed(() =>
  locations.value
    .filter((l) => l.is_active)
    .map((l) => ({ value: l.id, title: l.code, subtitle: t(`inventory.areas.${l.area_type}`) })),
)

async function loadLocations() {
  locations.value = []
  chosen.value = []
  if (!warehouse.value) return
  locations.value = (
    await listLocations({
      page: 1,
      pageSize: 200,
      ordering: 'code',
      filters: { warehouse: warehouse.value },
    })
  ).results
}

watch(formOpen, async (open) => {
  if (!open) return
  kind.value = 'cyclic'
  notes.value = ''
  error.value = ''
  if (!warehouses.value.length) {
    warehouses.value = (await listWarehouses({ page: 1, pageSize: 200, ordering: 'name' })).results
  }
  warehouse.value = warehouses.value[0]?.id ?? null
  await loadLocations()
})
watch(warehouse, (now, before) => {
  if (before !== null && now !== before) loadLocations()
})

async function submit() {
  const result = await formRef.value?.validate()
  if (!result?.valid || !warehouse.value) return
  saving.value = true
  error.value = ''
  try {
    const count = await openCount({
      warehouse: warehouse.value,
      kind: kind.value,
      locations: kind.value === 'cyclic' ? chosen.value : [],
      responsible: null,
      notes: notes.value,
    })
    formOpen.value = false
    show(count)
  } catch (e) {
    error.value = e instanceof ApiError ? e.message : t('common.saveError')
  } finally {
    saving.value = false
  }
}
const required = [(v: unknown) => (v !== null && v !== undefined) || t('validation.required')]
const someLocations = [
  (v: number[]) => kind.value !== 'cyclic' || v.length > 0 || t('inventory.counts.chooseLocations'),
]
</script>

<template>
  <v-container fluid class="module-page">
    <h1 class="mb-1">{{ $t('inventory.counts.title') }}</h1>
    <p class="text-medium-emphasis mb-4">{{ $t('inventory.counts.subtitle') }}</p>

    <ServerCrudTable
      :fetch-page="listCounts"
      :delete-item="async () => undefined"
      :headers="headers"
      :sort-by="[{ key: 'created_at', order: 'desc' }]"
      :search-placeholder="$t('inventory.counts.searchPlaceholder')"
      :filters="filters"
      filters-storage-key="inventory-counts"
      :empty-text="$t('inventory.counts.empty')"
      :no-results-text="$t('inventory.counts.noResults')"
      delete-title=""
      :delete-message="() => ''"
      deleted-text=""
      :hide-create="!isSupervisor"
      :can-delete="() => false"
      edit-icon="mdi-open-in-new"
      :edit-title="$t('inventory.counts.show')"
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
          <div class="text-caption text-medium-emphasis">{{ item.responsible_name }}</div>
        </div>
      </template>
      <template #[`item.warehouse`]="{ item }">
        <span :title="item.warehouse_name">{{ item.warehouse_code }}</span>
      </template>
      <template #[`item.kind`]="{ item }">{{ $t(`inventory.counts.kinds.${item.kind}`) }}</template>
      <template #[`item.locations_count`]="{ item }">
        {{ $t('inventory.counts.locations', { n: item.locations_count }) }} ·
        {{ $t('inventory.counts.readings', { n: item.readings_count }) }}
        <v-chip v-if="item.pending_count" color="warning" size="x-small" label class="ml-1">
          {{ $t('inventory.counts.pending', { n: item.pending_count }) }}
        </v-chip>
      </template>
      <template #[`item.accuracy`]="{ item }">
        {{ item.accuracy !== null ? `${$n(Number(item.accuracy), 'percentValue')}%` : '—' }}
      </template>
      <template #[`item.created_at`]="{ item }">{{
        d(new Date(item.created_at), 'dateTime')
      }}</template>
      <template #[`item.status`]="{ item }"><CountStatusChip :status="item.status" /></template>
    </ServerCrudTable>

    <FormDialog
      ref="formRef"
      v-model="formOpen"
      :title="$t('inventory.counts.new')"
      icon="mdi-clipboard-list-outline"
      max-width="640"
      :persistent="saving"
      @submit="submit"
    >
      <v-row dense>
        <v-col cols="12" md="7">
          <v-select
            v-model="warehouse"
            :items="warehouseOptions"
            :label="$t('inventory.fields.warehouse')"
            :rules="required"
            data-testid="count-warehouse"
          />
        </v-col>
        <v-col cols="12" md="5">
          <v-select
            v-model="kind"
            :items="
              (['cyclic', 'general'] as const).map((value) => ({
                value,
                title: $t(`inventory.counts.kinds.${value}`),
              }))
            "
            :label="$t('inventory.counts.kind')"
            data-testid="count-kind"
          />
        </v-col>
        <v-col v-if="kind === 'cyclic'" cols="12">
          <v-autocomplete
            v-model="chosen"
            :items="locationOptions"
            :label="$t('inventory.counts.scope')"
            :hint="$t('inventory.counts.scopeHint')"
            persistent-hint
            :rules="someLocations"
            multiple
            chips
            closable-chips
            data-testid="count-locations"
          />
        </v-col>
        <v-col v-else cols="12">
          <v-alert type="info" variant="tonal" density="compact">{{
            $t('inventory.counts.generalHint')
          }}</v-alert>
        </v-col>
        <v-col cols="12">
          <v-textarea v-model="notes" :label="$t('inventory.counts.notes')" rows="2" auto-grow />
        </v-col>
      </v-row>
      <v-alert v-if="error" type="error" variant="tonal" density="compact" class="mt-2">{{
        error
      }}</v-alert>
      <template #actions>
        <v-btn variant="text" :disabled="saving" @click="formOpen = false">{{
          $t('common.cancel')
        }}</v-btn>
        <v-btn type="submit" color="primary" variant="flat" :loading="saving">{{
          $t('inventory.counts.open')
        }}</v-btn>
      </template>
    </FormDialog>
  </v-container>
</template>
