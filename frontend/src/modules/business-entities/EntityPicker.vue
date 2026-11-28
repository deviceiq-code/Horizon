<script setup lang="ts">
/** Pick one business entity (v-model: id | null), searched on the server — e.g. a head office.
 * `role` offers only entities with it; `exclude` hides some (the entity being edited). */
import { computed } from 'vue'
import RemoteAutocomplete, { type RemoteOption } from '@/components/RemoteAutocomplete.vue'
import { formatTaxId } from '@/modules/customers/format'
import { listBusinessEntities, type EntityRef, type EntityRole } from './api'

const model = defineModel<number | null>({ required: true })
const props = withDefaults(
  defineProps<{
    label: string
    role?: EntityRole
    initialOption?: EntityRef | null
    exclude?: number[]
    rules?: ((value: unknown) => true | string)[]
    errorMessages?: string[]
  }>(),
  {
    role: undefined,
    initialOption: null,
    exclude: () => [],
    rules: () => [],
    errorMessages: undefined,
  },
)

function option(e: EntityRef): RemoteOption {
  return {
    value: e.id,
    title: e.trade_name || e.name,
    subtitle: [e.trade_name ? e.name : '', formatTaxId(e.tax_id, e.country)]
      .filter(Boolean)
      .join(' · '),
  }
}

const initial = computed<RemoteOption[]>(() =>
  props.initialOption ? [option(props.initialOption)] : [],
)

async function search(term: string) {
  const data = await listBusinessEntities({
    page: 1,
    pageSize: 50,
    search: term,
    ordering: 'name',
    filters: props.role ? { role: props.role } : {},
  })
  return data.results.map(option)
}
</script>

<template>
  <RemoteAutocomplete
    :model-value="model"
    :label="label"
    :search="search"
    :initial-options="initial"
    :exclude="exclude"
    :rules="rules"
    :error-messages="errorMessages"
    :no-data-text="$t('businessEntities.noneFound')"
    @update:model-value="model = typeof $event === 'number' ? $event : null"
  />
</template>
