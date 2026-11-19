<script setup lang="ts">
/** Pick one enabled manufacturer (v-model: id | null), searched on the server. */
import { computed } from 'vue'
import RemoteAutocomplete, { type RemoteOption } from '@/components/RemoteAutocomplete.vue'
import { listManufacturers } from './api'

const model = defineModel<number | null>({ required: true })
const props = withDefaults(
  defineProps<{
    label: string
    initialOption?: { id: number; name: string } | null
    rules?: ((value: unknown) => true | string)[]
    errorMessages?: string[]
  }>(),
  { initialOption: null, rules: () => [], errorMessages: undefined },
)

const initial = computed<RemoteOption[]>(() =>
  props.initialOption ? [{ value: props.initialOption.id, title: props.initialOption.name }] : [],
)

async function search(term: string) {
  const data = await listManufacturers({
    page: 1,
    pageSize: 50,
    search: term,
    ordering: 'name',
    filters: { is_enabled: true },
  })
  return data.results.map((m) => ({ value: m.id, title: m.name }))
}
</script>

<template>
  <RemoteAutocomplete
    :model-value="model"
    :label="label"
    :search="search"
    :initial-options="initial"
    :rules="rules"
    :error-messages="errorMessages"
    :no-data-text="$t('manufacturers.noneFound')"
    @update:model-value="model = typeof $event === 'number' ? $event : null"
  />
</template>
