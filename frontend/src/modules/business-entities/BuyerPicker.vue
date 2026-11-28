<script setup lang="ts">
/** Pick one active buyer (v-model: the Buyer role's id | null) — an entity with the Buyer role,
 * active in it and as an entity; searched on the server (e.g. a third-party sale's buyer). */
import { computed } from 'vue'
import RemoteAutocomplete, { type RemoteOption } from '@/components/RemoteAutocomplete.vue'
import { formatTaxId } from '@/modules/customers/format'
import { listBusinessEntities } from './api'

const model = defineModel<number | null>({ required: true })
const props = withDefaults(
  defineProps<{
    label: string
    /** The buyer already chosen: its role id and name */
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
  const data = await listBusinessEntities({
    page: 1,
    pageSize: 50,
    search: term,
    ordering: 'name',
    filters: { role: 'buyer', is_active: true },
  })
  return data.results
    .filter((e) => e.buyer)
    .map((e) => ({
      value: e.buyer!.id,
      title: e.trade_name || e.name,
      subtitle: [e.trade_name ? e.name : '', formatTaxId(e.tax_id, e.country)]
        .filter(Boolean)
        .join(' · '),
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
    :no-data-text="$t('businessEntities.noBuyers')"
    @update:model-value="model = typeof $event === 'number' ? $event : null"
  />
</template>
