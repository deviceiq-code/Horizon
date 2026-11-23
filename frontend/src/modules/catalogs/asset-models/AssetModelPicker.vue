<script setup lang="ts">
/** Pick one enabled asset model (v-model: id | null): "Dell Latitude 5440", the asset class as
 * subtitle. Emits `selected` with the whole model. Remount (:key) to start fresh. */
import { computed } from 'vue'
import RemoteAutocomplete, { type RemoteOption } from '@/components/RemoteAutocomplete.vue'
import { listAssetModels, type AssetModel } from './api'

const model = defineModel<number | null>({ required: true })
const props = withDefaults(
  defineProps<{
    label: string
    rules?: ((value: unknown) => true | string)[]
    errorMessages?: string[]
    /** Only models of this tracking (e.g. units for an asset entry) */
    tracking?: 'unit' | 'quantity'
    /** The chosen one, shown before any search ("Dell Latitude 5440") */
    initialOption?: { id: number; label: string } | null
  }>(),
  { rules: () => [], errorMessages: undefined, tracking: undefined, initialOption: null },
)
const emit = defineEmits<{ selected: [assetModel: AssetModel | null] }>()

const known = new Map<number, AssetModel>()
const initial = computed<RemoteOption[]>(() =>
  props.initialOption ? [{ value: props.initialOption.id, title: props.initialOption.label }] : [],
)

async function search(term: string) {
  const data = await listAssetModels({
    page: 1,
    pageSize: 50,
    search: term,
    ordering: 'manufacturer__name',
    filters: { is_enabled: true, ...(props.tracking ? { tracking: props.tracking } : {}) },
  })
  for (const m of data.results) known.set(m.id, m)
  return data.results.map((m) => ({
    value: m.id,
    title: `${m.manufacturer_name} ${m.name}`,
    subtitle: m.asset_class_detail.name,
  }))
}

function choose(value: unknown) {
  model.value = typeof value === 'number' ? value : null
  emit('selected', model.value === null ? null : (known.get(model.value) ?? null))
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
    :no-data-text="$t('assetModels.noneFound')"
    @update:model-value="choose($event)"
  />
</template>
