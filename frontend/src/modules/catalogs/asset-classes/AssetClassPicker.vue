<script setup lang="ts">
/**
 * Pick one enabled asset class (v-model: id | null), shown as "Excavators — Industry / Yellow
 * line" and searched on the server. Emits `selected` with the whole asset class (its
 * sub-vertical carries the terms and the specification template). Remount (:key) to start fresh.
 */
import { computed } from 'vue'
import RemoteAutocomplete, { type RemoteOption } from '@/components/RemoteAutocomplete.vue'
import { listAssetClasses, type AssetClass } from './api'

const model = defineModel<number | null>({ required: true })
const props = withDefaults(
  defineProps<{
    label: string
    initialOption?: AssetClass | null
    rules?: ((value: unknown) => true | string)[]
    errorMessages?: string[]
  }>(),
  { initialOption: null, rules: () => [], errorMessages: undefined },
)
const emit = defineEmits<{ selected: [assetClass: AssetClass | null] }>()

// Asset classes seen in search results, to hand the chosen one to the form
const known = new Map<number, AssetClass>()
if (props.initialOption) known.set(props.initialOption.id, props.initialOption)

const toOption = (a: AssetClass): RemoteOption => ({
  value: a.id,
  title: `${a.name} — ${a.sub_vertical_detail.label}`,
})
const initial = computed(() => (props.initialOption ? [toOption(props.initialOption)] : []))

async function search(term: string) {
  const data = await listAssetClasses({
    page: 1,
    pageSize: 50,
    search: term,
    ordering: 'name',
    filters: { is_enabled: true },
  })
  data.results.forEach((a) => known.set(a.id, a))
  return data.results.map(toOption)
}

function onUpdate(value: number | number[] | null) {
  const id = typeof value === 'number' ? value : null
  model.value = id
  emit('selected', id === null ? null : (known.get(id) ?? null))
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
    :no-data-text="$t('assetClasses.noneFound')"
    @update:model-value="onUpdate"
  />
</template>
