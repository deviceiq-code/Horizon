<script setup lang="ts">
/** Boxes, cages and pallets: created at a location with a new code (its label is printed then),
 * moved by reading them (Movement). They keep their history: deactivated, never deleted. */
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import ActiveChip from '@/components/ActiveChip.vue'
import ServerCrudTable from '@/components/ServerCrudTable.vue'
import { useColumnFilters } from '@/composables/useColumnFilters'
import { useNotificationsStore } from '@/stores/notifications'
import AreaChip from './AreaChip.vue'
import ContainerFormDialog from './ContainerFormDialog.vue'
import { CONTAINER_KINDS, listContainers, reprintContainer, type Container } from './api'
import { printLabels } from './labels'

const { t } = useI18n()
const notifications = useNotificationsStore()

const table = ref<{ reload: () => Promise<void> } | null>(null)

const { filters, clear: clearFilters } = useColumnFilters(['kind', 'is_active'] as const, [])
const kindOptions = computed(() =>
  CONTAINER_KINDS.map((value) => ({ value, title: t(`inventory.containerKinds.${value}`) })),
)
const statusOptions = computed(() => [
  { value: 'true', title: t('customers.status.active') },
  { value: 'false', title: t('customers.status.inactive') },
])

const headers = computed(() => [
  { title: t('inventory.containers.code'), key: 'code', width: 150 },
  { title: t('inventory.containers.kind'), key: 'kind', width: 180 },
  { title: t('inventory.fields.location'), key: 'current_location__code' },
  { title: t('inventory.containers.contents'), key: 'assets_count', sortable: false, width: 140 },
  { title: t('customers.fields.status'), key: 'is_active', width: 150 },
])

const formOpen = ref(false)
const editing = ref<Container | null>(null)

function openForm(container: Container | null) {
  editing.value = container
  formOpen.value = true
}

function labelOf(container: Container) {
  return {
    code: container.code,
    title: t(`inventory.containerKinds.${container.kind}`),
    subtitle: container.description,
  }
}

function onSaved(container: Container, created: boolean) {
  notifications.notify(
    t(created ? 'inventory.containers.created' : 'inventory.containers.updated', {
      code: container.code,
    }),
  )
  if (created) printLabels([labelOf(container)], container.code)
  table.value?.reload()
}

async function reprint(container: Container) {
  try {
    await reprintContainer(container.id)
    printLabels([labelOf(container)], container.code)
  } catch {
    notifications.notify(t('common.saveError'), 'error')
  }
}
</script>

<template>
  <ServerCrudTable
    ref="table"
    :fetch-page="listContainers"
    :delete-item="async () => undefined"
    :headers="headers"
    :sort-by="[{ key: 'code', order: 'desc' }]"
    :search-placeholder="$t('inventory.containers.searchPlaceholder')"
    :filters="filters"
    filters-storage-key="inventory-containers"
    :empty-text="$t('inventory.containers.empty')"
    :no-results-text="$t('inventory.containers.noResults')"
    delete-title=""
    :delete-message="() => ''"
    deleted-text=""
    :can-delete="() => false"
    @clear-filters="clearFilters"
    @create="openForm(null)"
    @edit="openForm"
  >
    <template #row-actions="{ item }">
      <v-btn
        icon="mdi-printer-outline"
        variant="text"
        size="small"
        :title="$t('inventory.labels.reprint')"
        :aria-label="$t('inventory.labels.reprint')"
        data-testid="reprint"
        @click="reprint(item)"
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
        data-testid="filter-kind"
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
    <template #[`item.code`]="{ item }">
      <div class="py-2">
        <div class="font-weight-medium">{{ item.code }}</div>
        <div v-if="item.description" class="text-caption text-medium-emphasis">
          {{ item.description }}
        </div>
      </div>
    </template>
    <template #[`item.kind`]="{ item }">
      {{ $t(`inventory.containerKinds.${item.kind}`) }}
    </template>
    <template #[`item.current_location__code`]="{ item }">
      <span class="d-inline-flex align-center ga-2">
        {{ item.current_location_detail.code }}
        <AreaChip :area="item.current_location_detail.area_type" size="x-small" />
      </span>
    </template>
    <template #[`item.assets_count`]="{ item }">
      {{ $t('inventory.containers.assetsInside', item.assets_count) }}
    </template>
    <template #[`item.is_active`]="{ item }">
      <ActiveChip :active="item.is_active" />
    </template>
  </ServerCrudTable>

  <ContainerFormDialog v-model="formOpen" :container="editing" @saved="onSaved" />
</template>
