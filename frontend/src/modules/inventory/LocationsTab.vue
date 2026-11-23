<script setup lang="ts">
/**
 * A warehouse's locations as a tree (area → aisle → shelf → position). Each code is the
 * parent's code + "-" + its segment and is printed on the location's label; the kind of area
 * says which asset statuses it takes. Writing: administrators and inventory supervisors.
 */
import { computed, onMounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { deleteErrorMessage } from '@/api'
import ConfirmDialog from '@/components/ConfirmDialog.vue'
import { listWarehouses, type Warehouse } from '@/modules/warehouses/api'
import { useNotificationsStore } from '@/stores/notifications'
import AreaChip from './AreaChip.vue'
import LocationFormDialog from './LocationFormDialog.vue'
import { deleteLocation, locationTree, type Location, type LocationNode } from './api'
import { printLabels, type Label } from './labels'

const { t } = useI18n()
const notifications = useNotificationsStore()

const warehouses = ref<Warehouse[]>([])
const warehouseId = ref<number | null>(null)
const tree = ref<LocationNode[]>([])
const loading = ref(false)
const loadError = ref(false)

const warehouse = computed(() => warehouses.value.find((w) => w.id === warehouseId.value) ?? null)
const warehouseOptions = computed(() =>
  warehouses.value.map((w) => ({ value: w.id, title: `${w.code} · ${w.name}` })),
)

onMounted(async () => {
  try {
    warehouses.value = (await listWarehouses({ page: 1, pageSize: 200, ordering: 'name' })).results
    warehouseId.value = warehouses.value[0]?.id ?? null
  } catch {
    loadError.value = true
  }
})

async function load() {
  if (warehouseId.value === null) {
    tree.value = []
    return
  }
  loading.value = true
  loadError.value = false
  try {
    tree.value = await locationTree(warehouseId.value)
  } catch {
    loadError.value = true
  } finally {
    loading.value = false
  }
}
watch(warehouseId, load)

// --- Create / edit / delete ----------------------------------------------------------------------

const formOpen = ref(false)
const editing = ref<Location | null>(null)
const parent = ref<Location | null>(null)

function openNew(under: Location | null) {
  editing.value = null
  parent.value = under
  formOpen.value = true
}

function openEdit(location: Location) {
  editing.value = location
  parent.value = null
  formOpen.value = true
}

function onSaved(location: Location, created: boolean) {
  notifications.notify(
    t(created ? 'inventory.locations.created' : 'inventory.locations.updated', {
      code: location.code,
    }),
  )
  load()
}

const deleting = ref<Location | null>(null)
const confirmOpen = ref(false)
const deleteInProgress = ref(false)

function askDelete(location: Location) {
  deleting.value = location
  confirmOpen.value = true
}

async function confirmDelete() {
  if (!deleting.value) return
  deleteInProgress.value = true
  try {
    await deleteLocation(deleting.value.id)
    notifications.notify(t('inventory.locations.deleted'))
    await load()
  } catch (error) {
    notifications.notify(deleteErrorMessage(error, t('common.deleteError')), 'error')
  } finally {
    confirmOpen.value = false
    deleteInProgress.value = false
  }
}

// --- Labels ------------------------------------------------------------------------------------

function labelOf(location: Location): Label {
  return {
    code: location.code,
    title: warehouse.value?.name ?? '',
    subtitle: location.description || t(`inventory.areas.${location.area_type}`),
  }
}

function flatten(nodes: LocationNode[]): LocationNode[] {
  return nodes.flatMap((node) => [node, ...flatten(node.children)])
}

function printBranch(node: LocationNode) {
  printLabels(flatten([node]).map(labelOf), node.code)
}

function printAll() {
  printLabels(
    flatten(tree.value)
      .filter((l) => l.is_active)
      .map(labelOf),
    warehouse.value?.code ?? '',
  )
}
</script>

<template>
  <div>
    <div class="d-flex flex-wrap align-center ga-3 mb-4">
      <v-select
        v-model="warehouseId"
        :items="warehouseOptions"
        :label="$t('inventory.fields.warehouse')"
        density="compact"
        hide-details
        style="min-width: 260px; max-width: 360px"
        data-testid="warehouse"
      />
      <v-spacer />
      <v-btn
        variant="text"
        prepend-icon="mdi-printer-outline"
        :disabled="!tree.length"
        data-testid="print-all"
        @click="printAll"
      >
        {{ $t('inventory.locations.printAll') }}
      </v-btn>
      <v-btn
        color="primary"
        prepend-icon="mdi-plus"
        :disabled="warehouseId === null"
        data-testid="new"
        @click="openNew(null)"
      >
        {{ $t('inventory.locations.newArea') }}
      </v-btn>
    </div>

    <v-alert v-if="loadError" type="error" variant="tonal" class="mb-4">
      {{ $t('common.loadError') }}
    </v-alert>

    <v-card :loading="loading">
      <v-treeview
        v-if="tree.length"
        :items="tree"
        item-value="id"
        item-title="code"
        item-children="children"
        open-all
        density="compact"
        data-testid="tree"
      >
        <template #title="{ item }">
          <span
            class="font-weight-medium"
            :class="{ 'text-disabled': !(item as LocationNode).is_active }"
          >
            {{ (item as LocationNode).code }}
          </span>
          <span v-if="(item as LocationNode).description" class="text-medium-emphasis ml-2">
            {{ (item as LocationNode).description }}
          </span>
        </template>
        <template #append="{ item }">
          <div class="d-flex align-center ga-2" @click.stop>
            <AreaChip :area="(item as LocationNode).area_type" size="x-small" />
            <v-chip
              v-if="(item as LocationNode).assets_count"
              size="x-small"
              variant="tonal"
              :title="$t('inventory.locations.assetsHere')"
            >
              {{ $t('inventory.locations.assetsCount', (item as LocationNode).assets_count) }}
            </v-chip>
            <v-chip v-if="!(item as LocationNode).is_active" size="x-small" variant="tonal" label>
              {{ $t('customers.status.inactive') }}
            </v-chip>
            <v-btn
              icon="mdi-plus"
              size="small"
              variant="text"
              :title="$t('inventory.locations.newChild')"
              :aria-label="$t('inventory.locations.newChild')"
              data-testid="add-child"
              @click="openNew(item as LocationNode)"
            />
            <v-btn
              icon="mdi-printer-outline"
              size="small"
              variant="text"
              :title="$t('inventory.locations.printBranch')"
              :aria-label="$t('inventory.locations.printBranch')"
              @click="printBranch(item as LocationNode)"
            />
            <v-btn
              icon="mdi-pencil-outline"
              size="small"
              variant="text"
              :title="$t('common.edit')"
              :aria-label="$t('common.edit')"
              data-testid="edit"
              @click="openEdit(item as LocationNode)"
            />
            <v-btn
              icon="mdi-delete-outline"
              size="small"
              variant="text"
              color="error"
              :title="$t('common.delete')"
              :aria-label="$t('common.delete')"
              data-testid="delete"
              @click="askDelete(item as LocationNode)"
            />
          </div>
        </template>
      </v-treeview>
      <v-card-text v-else-if="!loading" class="text-medium-emphasis" data-testid="empty">
        {{ $t('inventory.locations.empty') }}
      </v-card-text>
    </v-card>

    <LocationFormDialog
      v-model="formOpen"
      :location="editing"
      :parent="parent"
      :warehouse="warehouse"
      @saved="onSaved"
    />
    <ConfirmDialog
      v-model="confirmOpen"
      :title="$t('inventory.locations.deleteTitle')"
      :message="$t('inventory.locations.deleteConfirm', { code: deleting?.code ?? '' })"
      :confirm-text="$t('common.delete')"
      :loading="deleteInProgress"
      @confirm="confirmDelete"
    />
  </div>
</template>
