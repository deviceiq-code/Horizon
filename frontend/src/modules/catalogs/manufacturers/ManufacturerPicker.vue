<script setup lang="ts">
/** Pick one enabled manufacturer (v-model: id | null), searched on the server. `selected`
 * tells which one (its name) whenever the choice changes. */
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

const emit = defineEmits<{ selected: [manufacturer: { id: number; name: string } | null] }>()

/** Names of the manufacturers seen (initial option and search results), by id */
const names = new Map<number, string>()

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
  for (const m of data.results) names.set(m.id, m.name)
  return data.results.map((m) => ({ value: m.id, title: m.name }))
}

function choose(value: unknown) {
  model.value = typeof value === 'number' ? value : null
  if (props.initialOption) names.set(props.initialOption.id, props.initialOption.name)
  const id = model.value
  emit('selected', id === null ? null : { id, name: names.get(id) ?? '' })
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
    @update:model-value="choose($event)"
  />
</template>
