<script setup lang="ts">
/**
 * Search the current average prices and pick one to add (emits `pick`, then clears itself).
 * `exclude` hides the ones already added.
 */
import { ref } from 'vue'
import RemoteAutocomplete, { type RemoteOption } from '@/components/RemoteAutocomplete.vue'
import { listAveragePrices } from '@/modules/average-prices/api'

defineProps<{ label: string; exclude: number[] }>()
const emit = defineEmits<{ pick: [id: number] }>()

const selected = ref<number | null>(null)
// Remounted after each pick so the field starts empty again
const key = ref(0)

async function search(term: string): Promise<RemoteOption[]> {
  const data = await listAveragePrices({
    page: 1,
    pageSize: 20,
    search: term,
    ordering: 'asset_class__name',
  })
  return data.results.map((row) => ({
    value: row.id,
    title: `${row.manufacturer.name} ${row.model} · ${row.asset_class.name}`,
  }))
}

function onPick(value: number | number[] | null) {
  if (typeof value !== 'number') return
  emit('pick', value)
  selected.value = null
  key.value++
}
</script>

<template>
  <RemoteAutocomplete
    :key="key"
    :model-value="selected"
    :label="label"
    :search="search"
    :exclude="exclude"
    @update:model-value="onPick"
  />
</template>
