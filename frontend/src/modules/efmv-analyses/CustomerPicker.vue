<script setup lang="ts">
/**
 * Pick an active customer served by an account manager (as primary or secondary). Remount it
 * (via :key) when the account manager changes.
 */
import { computed } from 'vue'
import RemoteAutocomplete, { type RemoteOption } from '@/components/RemoteAutocomplete.vue'
import { listCustomers } from '@/modules/customers/api'
import type { CustomerRef } from './api'

const model = defineModel<number | null>({ required: true })
const props = defineProps<{
  label: string
  accountManager: number
  initialOptions?: CustomerRef[]
  rules?: ((value: unknown) => true | string)[]
  errorMessages?: string[]
  noDataText?: string
}>()

const toOption = (c: CustomerRef): RemoteOption => ({
  value: c.id,
  title: c.trade_name ? `${c.name} (${c.trade_name})` : c.name,
})
const initial = computed(() => (props.initialOptions ?? []).map(toOption))

async function search(term: string) {
  const data = await listCustomers({
    page: 1,
    pageSize: 20,
    search: term,
    ordering: 'entity__name',
    filters: { account_manager: props.accountManager, is_active: true },
  })
  return data.results.map(toOption)
}
</script>

<template>
  <RemoteAutocomplete
    v-model="model"
    :label="label"
    :search="search"
    :initial-options="initial"
    :rules="rules"
    :error-messages="errorMessages"
    :no-data-text="noDataText"
  />
</template>
