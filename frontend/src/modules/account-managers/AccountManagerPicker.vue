<script setup lang="ts">
/**
 * Pick one account manager (v-model: id | null) or several (multiple; v-model: id[]).
 * Searches the server as the user types. Pass `initialOptions` with the currently selected
 * managers so their names show before any search. Remount it (via :key) to start fresh.
 */
import { onMounted, ref } from 'vue'
import { listAccountManagers, type AccountManagerRef } from './api'

const model = defineModel<number | number[] | null>({ required: true })
const props = withDefaults(
  defineProps<{
    label: string
    multiple?: boolean
    initialOptions?: AccountManagerRef[]
    errorMessages?: string[]
    noDataText?: string
  }>(),
  { multiple: false, initialOptions: () => [], errorMessages: undefined, noDataText: undefined },
)

const options = ref<AccountManagerRef[]>([...props.initialOptions])
const loading = ref(false)
let timer: ReturnType<typeof setTimeout> | undefined
let lastRequest = 0

function selectedIds(): number[] {
  const value = model.value
  if (value === null || value === undefined) return []
  return Array.isArray(value) ? value : [value]
}

async function fetchOptions(term: string) {
  const request = ++lastRequest
  loading.value = true
  try {
    const data = await listAccountManagers({
      page: 1,
      pageSize: 20,
      search: term,
      ordering: 'full_name',
    })
    if (request !== lastRequest) return
    const results = data.results.map(({ id, full_name }) => ({ id, full_name }))
    // Keep the selected managers in the list so their names stay visible
    const ids = selectedIds()
    const selected = options.value.filter(
      (o) => ids.includes(o.id) && !results.some((r) => r.id === o.id),
    )
    options.value = [...selected, ...results]
  } catch {
    /* keep the current options; the field still works with what is loaded */
  } finally {
    if (request === lastRequest) loading.value = false
  }
}

function onSearch(term: string | null) {
  clearTimeout(timer)
  // In single mode Vuetify sets the search text to the selected name; no need to search it
  if (!props.multiple && term) {
    const selected = options.value.find((o) => o.id === model.value)
    if (selected && term === selected.full_name) return
  }
  timer = setTimeout(() => fetchOptions(term ?? ''), 300)
}

onMounted(() => fetchOptions(''))
</script>

<template>
  <v-autocomplete
    v-model="model"
    :items="options"
    item-title="full_name"
    item-value="id"
    :label="label"
    :multiple="multiple"
    :chips="multiple"
    :closable-chips="multiple"
    :loading="loading"
    :error-messages="errorMessages"
    :no-data-text="noDataText"
    no-filter
    clearable
    @update:search="onSearch"
  />
</template>
