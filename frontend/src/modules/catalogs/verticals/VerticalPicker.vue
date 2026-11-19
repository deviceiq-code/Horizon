<script setup lang="ts">
/**
 * Pick one business vertical (v-model: id | null) or several (multiple; v-model: id[]).
 * Offers only enabled verticals, searching the server as the user types; verticals already
 * selected stay listed (marked) even if disabled since. Pass `initialOptions` with the current
 * selection. Remount it (via :key) to start fresh.
 */
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import RemoteAutocomplete, { type RemoteOption } from '@/components/RemoteAutocomplete.vue'
import { listVerticals, type VerticalRef } from './api'

const model = defineModel<number | number[] | null>({ required: true })
const props = withDefaults(
  defineProps<{
    label: string
    multiple?: boolean
    initialOptions?: VerticalRef[]
    rules?: ((value: unknown) => true | string)[]
    errorMessages?: string[]
  }>(),
  { multiple: false, initialOptions: () => [], rules: () => [], errorMessages: undefined },
)

const { t } = useI18n()

const toOption = (v: VerticalRef): RemoteOption => ({
  value: v.id,
  title: v.is_enabled ? v.name : `${v.name} (${t('verticals.status.disabled')})`,
})
const initial = computed(() => props.initialOptions.map(toOption))

async function search(term: string) {
  const data = await listVerticals({
    page: 1,
    pageSize: 50,
    search: term,
    ordering: 'name',
    filters: { is_enabled: true },
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
    :rules="rules"
    :error-messages="errorMessages"
    :no-data-text="t('verticals.noneFound')"
  />
</template>
