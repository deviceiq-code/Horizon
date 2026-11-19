<script setup lang="ts">
/**
 * Pick one account manager (v-model: id | null) or several (multiple; v-model: id[]).
 * Searches the server as the user types. Pass `initialOptions` with the currently selected
 * managers so their names show before any search. Remount it (via :key) to start fresh.
 */
import { computed } from 'vue'
import RemoteAutocomplete, { type RemoteOption } from '@/components/RemoteAutocomplete.vue'
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

const toOption = (m: AccountManagerRef): RemoteOption => ({ value: m.id, title: m.full_name })
const initial = computed(() => props.initialOptions.map(toOption))

async function search(term: string) {
  const data = await listAccountManagers({
    page: 1,
    pageSize: 20,
    search: term,
    ordering: 'full_name',
  })
  return data.results.map(toOption)
}
</script>

<template>
  <RemoteAutocomplete
    v-model="model"
    :label="label"
    :search="search"
    :multiple="multiple"
    :initial-options="initial"
    :error-messages="errorMessages"
    :no-data-text="noDataText"
  />
</template>
