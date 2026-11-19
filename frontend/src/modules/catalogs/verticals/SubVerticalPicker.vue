<script setup lang="ts">
/**
 * Pick one sub-vertical, shown as "Vertical / Sub-vertical" (v-model: id | null). Offers only
 * sub-verticals of enabled verticals, searching the server as the user types; the current one
 * stays listed (marked) if its vertical was disabled since. Remount it (via :key) to start fresh.
 */
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import RemoteAutocomplete, { type RemoteOption } from '@/components/RemoteAutocomplete.vue'
import { listSubVerticals, type SubVerticalOption } from './api'

const model = defineModel<number | null>({ required: true })
const props = withDefaults(
  defineProps<{
    label: string
    initialOption?: SubVerticalOption | null
    rules?: ((value: unknown) => true | string)[]
    errorMessages?: string[]
  }>(),
  { initialOption: null, rules: () => [], errorMessages: undefined },
)

const { t } = useI18n()

const toOption = (s: SubVerticalOption): RemoteOption => ({
  value: s.id,
  title: s.vertical.is_enabled ? s.label : `${s.label} (${t('verticals.status.disabled')})`,
})
const initial = computed(() => (props.initialOption ? [toOption(props.initialOption)] : []))

async function search(term: string) {
  const data = await listSubVerticals({
    page: 1,
    pageSize: 50,
    search: term,
    filters: { is_enabled: true },
  })
  return data.results.map(toOption)
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
    :no-data-text="t('verticals.noneFound')"
    @update:model-value="model = typeof $event === 'number' ? $event : null"
  />
</template>
