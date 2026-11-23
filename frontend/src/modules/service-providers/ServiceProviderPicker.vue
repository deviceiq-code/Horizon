<script setup lang="ts">
/** Pick one active service provider (v-model: id | null), searched on the server; `service`
 * offers only those providing it (e.g. warehousing for an outsourced warehouse). */
import { computed } from 'vue'
import RemoteAutocomplete, { type RemoteOption } from '@/components/RemoteAutocomplete.vue'
import { formatTaxId } from '@/modules/customers/format'
import { listServiceProviders, type ServiceKind } from './api'

const model = defineModel<number | null>({ required: true })
const props = withDefaults(
  defineProps<{
    label: string
    service?: ServiceKind
    initialOption?: { id: number; name: string } | null
    rules?: ((value: unknown) => true | string)[]
    errorMessages?: string[]
  }>(),
  { service: undefined, initialOption: null, rules: () => [], errorMessages: undefined },
)

const initial = computed<RemoteOption[]>(() =>
  props.initialOption ? [{ value: props.initialOption.id, title: props.initialOption.name }] : [],
)

async function search(term: string) {
  const data = await listServiceProviders({
    page: 1,
    pageSize: 50,
    search: term,
    ordering: 'name',
    filters: { is_active: true, ...(props.service ? { service: props.service } : {}) },
  })
  return data.results.map((p) => ({
    value: p.id,
    // The trade name when it has one (as the API's service_provider_detail)
    title: p.trade_name || p.name,
    subtitle: [p.trade_name ? p.name : '', formatTaxId(p.tax_id, p.country)]
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
    :no-data-text="$t('serviceProviders.noneFound')"
    @update:model-value="model = typeof $event === 'number' ? $event : null"
  />
</template>
