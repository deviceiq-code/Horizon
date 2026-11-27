import { ref, watch, type Ref } from 'vue'
import type { ListParams, Paginated } from '@/api'

export interface SortItem {
  key: string
  order?: boolean | 'asc' | 'desc'
}

export interface ServerTableOptions {
  /** Initial sort, e.g. [{ key: 'name', order: 'asc' }] */
  sortBy: SortItem[]
  /** Column key → API ordering field, when they differ (e.g. a related object's name) */
  orderingFields?: Record<string, string>
  pageSize?: number
  /** Search the grid opens with (e.g. ?search= from the centralized search) */
  initialSearch?: string
  /** Wait this long after the user stops typing before searching */
  searchDelayMs?: number
  /**
   * Column filters, sent as query parameters (empty values are left out). Any change goes back
   * to the first page and reloads.
   */
  filters?: () => Record<string, string | number | boolean | null | undefined>
}

/** The filters with a value (what is sent to the API). */
export function activeFilters(
  filters: Record<string, string | number | boolean | null | undefined> | undefined,
): Record<string, string | number | boolean> {
  return Object.fromEntries(
    Object.entries(filters ?? {}).filter(
      ([, value]) => value !== null && value !== undefined && value !== '',
    ),
  ) as Record<string, string | number | boolean>
}

/**
 * State and loading logic for a <v-data-table-server> grid: server-side pagination, sorting
 * and debounced search. Bind page/itemsPerPage/sortBy with v-model, :search="search", and call
 * load() from @update:options (the table emits it on mount and whenever any of them change).
 */
export function useServerTable<T>(
  fetchPage: (params: ListParams) => Promise<Paginated<T>>,
  options: ServerTableOptions,
) {
  const items = ref([]) as Ref<T[]>
  const total = ref(0)
  const loading = ref(false)
  const loadError = ref(false)
  const page = ref(1)
  const itemsPerPage = ref(options.pageSize ?? 25)
  const sortBy = ref<SortItem[]>(options.sortBy)

  const searchInput = ref<string | null>(options.initialSearch ?? '')
  // debounced copy of searchInput, bound to the table
  const search = ref((options.initialSearch ?? '').trim())
  let searchTimer: ReturnType<typeof setTimeout> | undefined
  watch(searchInput, (value) => {
    clearTimeout(searchTimer)
    searchTimer = setTimeout(
      () => (search.value = (value ?? '').trim()),
      options.searchDelayMs ?? 300,
    )
  })

  let lastRequest = 0

  // Filters changed: back to the first page (the table reloads when the page changes)
  if (options.filters) {
    watch(
      () => JSON.stringify(activeFilters(options.filters?.())),
      () => {
        if (page.value !== 1) page.value = 1
        else load()
      },
    )
  }

  async function load() {
    const request = ++lastRequest
    const sort = sortBy.value[0]
    const field = sort ? (options.orderingFields?.[sort.key] ?? sort.key) : undefined
    loading.value = true
    loadError.value = false
    try {
      const data = await fetchPage({
        page: page.value,
        pageSize: itemsPerPage.value,
        search: search.value,
        ...(options.filters ? { filters: activeFilters(options.filters()) } : {}),
        ordering: field ? `${sort?.order === 'desc' ? '-' : ''}${field}` : undefined,
      })
      if (request !== lastRequest) return // a newer request already answered
      items.value = data.results
      total.value = data.count
    } catch {
      if (request !== lastRequest) return
      items.value = []
      total.value = 0
      loadError.value = true
    } finally {
      if (request === lastRequest) loading.value = false
    }
  }

  /** After deleting a row: step back a page if it was the last row on it, else reload. */
  async function reloadAfterDelete() {
    if (items.value.length === 1 && page.value > 1) {
      page.value -= 1 // the table reloads on its own when the page changes
    } else {
      await load()
    }
  }

  return {
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
  }
}
