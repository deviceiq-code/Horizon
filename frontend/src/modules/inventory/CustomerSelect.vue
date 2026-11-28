<script setup lang="ts">
/** Pick an active customer (any account manager), searched on the server. */
import { computed } from 'vue'
import RemoteAutocomplete, { type RemoteOption } from '@/components/RemoteAutocomplete.vue'
import { listCustomers } from '@/modules/customers/api'

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
  const data = await listCustomers({
    page: 1,
    pageSize: 30,
    search: term,
    ordering: 'entity__name',
    filters: { is_active: true },
  })
  return data.results.map((c) => ({
    value: c.id,
    title: c.trade_name || c.name,
    subtitle: c.trade_name ? c.name : undefined,
  }))
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
    @update:model-value="model = typeof $event === 'number' ? $event : null"
  />
</template>
