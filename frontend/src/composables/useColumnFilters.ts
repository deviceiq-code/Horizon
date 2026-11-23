/**
 * Column filters of a ServerCrudTable (`filters`, sent as query parameters). Text filters are
 * typed into `typed.<key>` and applied after a short pause; the others are set on `filters`
 * directly. `clear()` empties them all (the grid's `clear-filters`).
 */
import { reactive, watch } from 'vue'

export type FilterValue = string | number | null

export function useColumnFilters<K extends string>(keys: readonly K[], textKeys: readonly K[]) {
  const empty = () => Object.fromEntries(keys.map((key) => [key, null])) as Record<K, FilterValue>
  const filters = reactive(empty()) as Record<K, FilterValue>
  const typed = reactive(Object.fromEntries(textKeys.map((key) => [key, '']))) as Record<
    K,
    string | null
  >

  const timers = new Map<K, ReturnType<typeof setTimeout>>()
  for (const key of textKeys) {
    watch(
      () => typed[key],
      (value) => {
        clearTimeout(timers.get(key))
        timers.set(
          key,
          setTimeout(() => (filters[key] = (value ?? '').trim() || null), 350),
        )
      },
    )
  }

  function clear() {
    for (const timer of timers.values()) clearTimeout(timer)
    for (const key of textKeys) typed[key] = ''
    Object.assign(filters, empty())
  }

  return { filters, typed, clear }
}
