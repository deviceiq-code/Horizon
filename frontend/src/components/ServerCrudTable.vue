<script setup lang="ts" generic="T extends { id: number }">
/**
 * Standard CRUD grid: search box + "New" button, server-side paginated/sorted table with edit
 * and delete actions, delete confirmation and notifications. The page provides the columns,
 * texts and cell slots (`item.<key>`), opens its own form on `create`/`edit`, and calls the
 * exposed `reload()` after saving. With `expandable`, rows it accepts get an expand toggle and
 * show the `expanded-row` slot ({ item, columns }).
 */
import { computed, ref, useSlots } from 'vue'
import { useI18n } from 'vue-i18n'
import type { DataTableHeader } from 'vuetify'
import { deleteErrorMessage, type ListParams, type Paginated } from '@/api'
import ConfirmDialog from '@/components/ConfirmDialog.vue'
import { useServerTable, type SortItem } from '@/composables/useServerTable'
import { useNotificationsStore } from '@/stores/notifications'

const props = defineProps<{
  fetchPage: (params: ListParams) => Promise<Paginated<T>>
  deleteItem: (id: number) => Promise<void>
  /** Columns, without the actions column (added here) */
  headers: DataTableHeader[]
  sortBy: SortItem[]
  /** Column key → API ordering field, when they differ */
  orderingFields?: Record<string, string>
  searchPlaceholder: string
  emptyText: string
  noResultsText: string
  deleteTitle: string
  deleteMessage: (item: T) => string
  deletedText: string
  /** Edit button look (e.g. "New version" where rows are never edited in place) */
  editIcon?: string
  editTitle?: string
  /** Which rows can be expanded (shows the expanded-row slot); none when absent */
  expandable?: (item: T) => boolean
}>()

const emit = defineEmits<{ create: []; edit: [item: T] }>()

const { t } = useI18n()
const notifications = useNotificationsStore()

const {
  items,
  total,
  loading,
  loadError,
  page,
  itemsPerPage,
  sortBy,
  searchInput,
  search,
  load,
  reloadAfterDelete,
} = useServerTable(props.fetchPage, {
  sortBy: props.sortBy,
  orderingFields: props.orderingFields,
})

// Expanded rows by id, so they stay open when the page reloads
const expanded = ref<string[]>([])

const allHeaders = computed(() => [
  ...(props.expandable ? [{ title: '', key: 'data-table-expand', width: 48 }] : []),
  ...props.headers,
  {
    title: t('common.actions'),
    key: 'actions',
    sortable: false,
    align: 'end' as const,
    minWidth: '120px',
    nowrap: true,
  },
])

// --- Delete ----------------------------------------------------------------------------------

const deleting = ref<T | null>(null)
const confirmOpen = ref(false)
const deleteInProgress = ref(false)

function askDelete(item: T) {
  deleting.value = item
  confirmOpen.value = true
}

async function confirmDelete() {
  if (!deleting.value) return
  deleteInProgress.value = true
  try {
    await props.deleteItem(deleting.value.id)
    notifications.notify(props.deletedText)
    confirmOpen.value = false
    await reloadAfterDelete()
  } catch (error) {
    notifications.notify(deleteErrorMessage(error, t('common.deleteError')), 'error')
    confirmOpen.value = false
  } finally {
    deleteInProgress.value = false
  }
}

// Only item.<key> cell slots go to the table (row-actions is used above)
const slots = useSlots()
const cellSlots = computed(() =>
  Object.fromEntries(Object.entries(slots).filter(([name]) => name.startsWith('item.'))),
)

defineExpose({ reload: load })
</script>

<template>
  <div>
    <div class="d-flex flex-wrap align-center ga-3 mb-4">
      <v-text-field
        v-model="searchInput"
        :placeholder="searchPlaceholder"
        :aria-label="$t('common.search')"
        prepend-inner-icon="mdi-magnify"
        density="compact"
        clearable
        hide-details
        class="mr-auto"
        style="min-width: 260px; max-width: 400px"
        data-testid="search"
      />
      <v-btn color="primary" prepend-icon="mdi-plus" data-testid="new" @click="emit('create')">
        {{ $t('common.new') }}
      </v-btn>
    </div>

    <v-alert v-if="loadError" type="error" variant="tonal" class="mb-4">
      {{ $t('common.loadError') }}
      <template #append>
        <v-btn variant="text" size="small" @click="load">{{ $t('common.retry') }}</v-btn>
      </template>
    </v-alert>

    <v-card>
      <v-data-table-server
        v-model:page="page"
        v-model:items-per-page="itemsPerPage"
        v-model:sort-by="sortBy"
        :headers="allHeaders"
        :items="items"
        :items-length="total"
        :loading="loading"
        :search="search"
        :items-per-page-options="[10, 25, 50, 100]"
        :no-data-text="search ? noResultsText : emptyText"
        v-model:expanded="expanded"
        item-value="id"
        :show-expand="!!expandable"
        must-sort
        hover
        @update:options="load"
      >
        <!-- Cell slots provided by the page (item.<key>) -->
        <template v-for="(_, name) in cellSlots" #[name]="slotProps">
          <slot :name="name" v-bind="slotProps ?? {}" />
        </template>

        <template
          v-if="expandable"
          #[`item.data-table-expand`]="{ item, internalItem, isExpanded, toggleExpand }"
        >
          <v-btn
            v-if="expandable(item)"
            :icon="isExpanded(internalItem) ? 'mdi-chevron-up' : 'mdi-chevron-down'"
            variant="text"
            size="small"
            :aria-label="$t('common.expand')"
            :aria-expanded="isExpanded(internalItem)"
            data-testid="expand"
            @click="toggleExpand(internalItem)"
          />
        </template>
        <template v-if="expandable" #expanded-row="{ item, columns }">
          <tr>
            <td :colspan="columns.length" class="bg-surface-light pa-0">
              <slot name="expanded-row" :item="item" :columns="columns" />
            </td>
          </tr>
        </template>

        <template #[`item.actions`]="{ item }">
          <!-- Extra actions provided by the page, before edit/delete -->
          <slot name="row-actions" :item="item" />
          <v-btn
            :icon="editIcon ?? 'mdi-pencil-outline'"
            variant="text"
            size="small"
            :aria-label="editTitle ?? $t('common.edit')"
            :title="editTitle ?? $t('common.edit')"
            data-testid="edit"
            @click="emit('edit', item)"
          />
          <v-btn
            icon="mdi-delete-outline"
            variant="text"
            size="small"
            color="error"
            :aria-label="$t('common.delete')"
            :title="$t('common.delete')"
            data-testid="delete"
            @click="askDelete(item)"
          />
        </template>
      </v-data-table-server>
    </v-card>

    <ConfirmDialog
      v-model="confirmOpen"
      :title="deleteTitle"
      :message="deleting ? deleteMessage(deleting) : ''"
      :confirm-text="$t('common.delete')"
      :loading="deleteInProgress"
      @confirm="confirmDelete"
    />
  </div>
</template>
