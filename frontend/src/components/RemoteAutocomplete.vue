<script setup lang="ts">
/**
 * Pick one record (v-model: id | null) or several (multiple; v-model: id[]) from a list that
 * lives on the server, searching as the user types. Pass `initialOptions` with the records
 * already selected so their names show before any search. Remount it (via :key) to start fresh.
 * Wrapped by module pickers such as AccountManagerPicker and VerticalPicker.
 *
 * Multiple mode: each chip has its own X and there is no "clear all" button (too easy to hit
 * by mistake next to the chips); the typed text is cleared after each pick.
 */
import { computed, onMounted, ref } from 'vue'
import { showInDropdown } from './remoteFilter'

export interface RemoteOption {
  value: number
  title: string
}

const model = defineModel<number | number[] | null>({ required: true })
const props = withDefaults(
  defineProps<{
    label: string
    /** Options matching the typed text (empty text: the first options) */
    search: (term: string) => Promise<RemoteOption[]>
    multiple?: boolean
    initialOptions?: RemoteOption[]
    /** Records never offered in the dropdown (e.g. one already chosen in another field) */
    exclude?: number[]
    rules?: ((value: unknown) => true | string)[]
    errorMessages?: string[]
    noDataText?: string
  }>(),
  {
    multiple: false,
    initialOptions: () => [],
    exclude: () => [],
    rules: () => [],
    errorMessages: undefined,
    noDataText: undefined,
  },
)

const options = ref<RemoteOption[]>([...props.initialOptions])
const offered = computed(() =>
  options.value.filter(
    (o) => !props.exclude.includes(o.value) || selectedValues().includes(o.value),
  ),
)
const loading = ref(false)
let timer: ReturnType<typeof setTimeout> | undefined
let lastRequest = 0
// Values returned by the latest search (they always show in the dropdown)
let latestResults = new Set<number>()

/** Hides selected records kept only for their chips when they don't match the typed text. */
function filter(_value: string, query: string, item?: { raw: unknown }): boolean {
  const option = item?.raw as RemoteOption | undefined
  return option ? showInDropdown(option, query, latestResults) : true
}

function selectedValues(): number[] {
  const value = model.value
  if (value === null || value === undefined) return []
  return Array.isArray(value) ? value : [value]
}

async function fetchOptions(term: string) {
  const request = ++lastRequest
  loading.value = true
  try {
    const results = await props.search(term)
    if (request !== lastRequest) return
    latestResults = new Set(results.map((r) => r.value))
    // Keep the selected records in the list so their chips keep a title
    const selected = selectedValues()
    const kept = options.value.filter(
      (o) => selected.includes(o.value) && !results.some((r) => r.value === o.value),
    )
    options.value = [...kept, ...results]
  } catch {
    /* keep the current options; the field still works with what is loaded */
  } finally {
    if (request === lastRequest) loading.value = false
  }
}

function onSearch(term: string | null) {
  clearTimeout(timer)
  // In single mode Vuetify fills the search text with the chosen title (possibly before the
  // model updates). Searching for it would shrink the list to that one record, so skip it:
  // a text equal to a loaded option's title adds nothing new.
  if (!props.multiple && term && options.value.some((o) => o.title === term)) return
  timer = setTimeout(() => fetchOptions(term ?? ''), 300)
}

onMounted(() => fetchOptions(''))
</script>

<template>
  <v-autocomplete
    v-model="model"
    :items="offered"
    item-title="title"
    item-value="value"
    :label="label"
    :rules="rules"
    :multiple="multiple"
    :chips="multiple"
    :closable-chips="multiple"
    :loading="loading"
    :error-messages="errorMessages"
    :no-data-text="noDataText"
    :custom-filter="filter"
    :clearable="!multiple"
    :clear-on-select="multiple"
    @update:search="onSearch"
  />
</template>
