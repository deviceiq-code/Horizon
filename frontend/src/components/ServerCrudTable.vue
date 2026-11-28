<script setup lang="ts" generic="T extends { id: number }">
/**
 * Standard CRUD grid: search box + "New" button, server-side paginated/sorted table with edit
 * and delete actions, delete confirmation and notifications. The page provides the columns,
 * texts and cell slots (`item.<key>`), opens its own form on `create`/`edit`, and calls the
 * exposed `reload()` after saving. With `expandable`, rows it accepts get an expand toggle and
 * show the `expanded-row` slot ({ item, columns }). Column filters: pass `filters` (sent to the
 * API as query parameters) and a `filter.<key>` slot per filtered column; they show in a row
 * under the titles, turned on and off with the "Filters" button (remembered per grid with
 * `filtersStorageKey`, kept with the account; turning them off clears them). The `toolbar`
 * slot adds buttons between Filters and New; `selectable` shows a checkbox per row
 * (v-model:selected — ids, kept across pages; the page limits how many).
 */
import { computed, ref, useSlots } from 'vue'
import { useI18n } from 'vue-i18n'
import type { DataTableHeader } from 'vuetify'
import { deleteErrorMessage, type ListParams, type Paginated } from '@/api'
import ConfirmDialog from '@/components/ConfirmDialog.vue'
import { activeFilters, useServerTable, type SortItem } from '@/composables/useServerTable'
import { useNotificationsStore } from '@/stores/notifications'
import { usePreferencesStore } from '@/stores/preferences'

/** An action of a row (a button, or an item of its "…" menu) */
export interface RowAction {
  key: string
  icon: string
  title: string
  color?: string
  onClick: () => void
}

/** More actions than this in a row: all of them go into the "…" menu */
const MAX_INLINE_ACTIONS = 3

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
  /** Column filters (query parameters); edit them in `filter.<key>` slots */
  filters?: Record<string, string | number | boolean | null | undefined>
  /** Remembers in this browser whether the filter row is shown (e.g. "average-prices") */
  filtersStorageKey?: string
  /** Show the filter row from the start (e.g. the page was opened with a filter) */
  showFiltersAtStart?: boolean
  /** Rows that can be edited / deleted (all when absent); e.g. not a system record */
  /** Hides the "New" button (e.g. records created elsewhere) */
  hideCreate?: boolean
  canEdit?: (item: T) => boolean
  canDelete?: (item: T) => boolean
  /** Rows show a checkbox (v-model:selected = their ids; no "select all") */
  selectable?: boolean
  /** A row's own actions, before edit and delete. Up to MAX_INLINE_ACTIONS in all: buttons;
   * more: every one of them in a "…" menu */
  rowActionsList?: (item: T) => RowAction[]
}>()

/** Ids of the selected rows (with `selectable`), kept across pages */
const selected = defineModel<number[]>('selected', { default: () => [] })

// `open`: a row double-clicked (e.g. its details)
const emit = defineEmits<{ create: []; edit: [item: T]; open: [item: T]; clearFilters: [] }>()

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
  // Opened from the centralized search (?search= in the address): already searching for it
  initialSearch: new URLSearchParams(window.location.search).get('search') ?? '',
  sortBy: props.sortBy,
  orderingFields: props.orderingFields,
  filters: props.filters ? () => props.filters ?? {} : undefined,
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
const hasFilterRow = computed(() => Object.keys(slots).some((name) => name.startsWith('filter.')))
const filtering = computed(() => Object.keys(activeFilters(props.filters)).length > 0)

// Filter row on/off, kept with the account (preferences' ui_state): the same on any computer
const preferences = usePreferencesStore()
const storageKey = props.filtersStorageKey
const filtersShown = ref(
  (!!storageKey && !!preferences.uiState.filters?.[storageKey]) || !!props.showFiltersAtStart,
)

function toggleFilters() {
  filtersShown.value = !filtersShown.value
  // Hidden filters must not keep filtering
  if (!filtersShown.value && filtering.value) emit('clearFilters')
  if (storageKey) {
    const shown = filtersShown.value
    preferences.saveUiState((state) => ({
      ...state,
      filters: { ...state.filters, [storageKey]: shown },
    }))
  }
}

defineExpose({ reload: load })

/** Every action of a row: its own, then edit and delete (when allowed) */
function actionsOf(item: T): RowAction[] {
  const actions = [...(props.rowActionsList?.(item) ?? [])]
  if (!props.canEdit || props.canEdit(item)) {
    actions.push({
      key: 'edit',
      icon: props.editIcon ?? 'mdi-pencil-outline',
      title: props.editTitle ?? t('common.edit'),
      onClick: () => emit('edit', item),
    })
  }
  if (!props.canDelete || props.canDelete(item)) {
    actions.push({
      key: 'delete',
      icon: 'mdi-delete-outline',
      title: t('common.delete'),
      color: 'error',
      onClick: () => askDelete(item),
    })
  }
  return actions
}

function inlineActions(item: T): RowAction[] {
  const all = actionsOf(item)
  return all.length > MAX_INLINE_ACTIONS ? [] : all
}

function menuActions(item: T): RowAction[] {
  const all = actionsOf(item)
  return all.length > MAX_INLINE_ACTIONS ? all : []
}
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
      <v-btn
        v-if="hasFilterRow"
        :variant="filtersShown ? 'tonal' : 'text'"
        :color="filtersShown ? 'primary' : undefined"
        :prepend-icon="filtersShown ? 'mdi-filter-off-outline' : 'mdi-filter-outline'"
        :aria-pressed="filtersShown"
        data-testid="toggle-filters"
        @click="toggleFilters"
      >
        {{ $t(filtersShown ? 'common.hideFilters' : 'common.showFilters') }}
      </v-btn>
      <!-- Page buttons between Filters and New (e.g. Compare) -->
      <slot name="toolbar" />
      <v-btn
        v-if="!hideCreate"
        color="primary"
        prepend-icon="mdi-plus"
        data-testid="new"
        @click="emit('create')"
      >
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
        v-model="selected"
        :show-select="selectable"
        item-value="id"
        :show-expand="!!expandable"
        must-sort
        hover
        @update:options="load"
        @dblclick:row="(_event: Event, row: { item: T }) => emit('open', row.item)"
      >
        <!-- Selecting is row by row (pages limit how many) -->
        <template #[`header.data-table-select`] />
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
        <!-- Column filters, under the titles -->
        <template v-if="hasFilterRow && filtersShown" #thead="{ columns }">
          <thead class="filter-row" data-testid="filter-row">
            <tr>
              <th v-for="column in columns" :key="String(column.key)" class="filter-cell">
                <slot v-if="column.key === 'actions'" name="filter.actions">
                  <v-btn
                    v-if="filtering"
                    variant="text"
                    size="small"
                    prepend-icon="mdi-filter-remove-outline"
                    data-testid="clear-filters"
                    @click="emit('clearFilters')"
                  >
                    {{ $t('common.clearFilters') }}
                  </v-btn>
                </slot>
                <slot v-else :name="`filter.${String(column.key)}`" />
              </th>
            </tr>
          </thead>
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
            v-for="action in inlineActions(item)"
            :key="action.key"
            :icon="action.icon"
            variant="text"
            size="small"
            :color="action.color"
            :aria-label="action.title"
            :title="action.title"
            :data-testid="action.key"
            @click="action.onClick"
          />
          <!-- More than three: all of them in a menu -->
          <v-menu v-if="menuActions(item).length" location="bottom end">
            <template #activator="{ props: menu }">
              <v-btn
                v-bind="menu"
                icon="mdi-dots-horizontal"
                variant="text"
                size="small"
                :aria-label="$t('common.moreActions')"
                :title="$t('common.moreActions')"
                data-testid="more-actions"
              />
            </template>
            <v-list density="compact" data-testid="more-actions-menu">
              <v-list-item
                v-for="action in menuActions(item)"
                :key="action.key"
                :prepend-icon="action.icon"
                :title="action.title"
                :base-color="action.color"
                :data-testid="action.key"
                @click="action.onClick"
              />
            </v-list>
          </v-menu>
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

<style scoped>
.filter-row .filter-cell {
  height: auto;
  padding-top: 4px;
  padding-bottom: 8px;
  vertical-align: top;
  font-weight: normal;
}
</style>
