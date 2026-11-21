<script setup lang="ts">
/**
 * Search the current average prices and pick one (emits `pick`, then clears itself).
 * Every asset is offered, also those already in the scenario (it may repeat). Options read "Model (specification values)", with
 * the manufacturer and asset class below.
 */
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'
import RemoteAutocomplete, { type RemoteOption } from '@/components/RemoteAutocomplete.vue'
import { listAveragePrices, type AveragePrice } from '@/modules/average-prices/api'
import { specSummary } from '@/modules/average-prices/specText'

const props = defineProps<{
  label: string
  /** Only assets of this vertical / sub-vertical (the scenario's) */
  vertical?: number | null
  subVertical?: number | null
}>()
const emit = defineEmits<{ pick: [id: number] }>()

const { t, n } = useI18n()

/** "320 GC (2500 h, Steel, Cab: Yes)": the filled specifications, in template order. */
function optionTitle(row: AveragePrice): string {
  const specs = specSummary(row.specs, t, n)
  return specs ? `${row.model} (${specs})` : row.model
}

const selected = ref<number | null>(null)
// Remounted after each pick so the field starts empty again
const key = ref(0)

async function search(term: string): Promise<RemoteOption[]> {
  const data = await listAveragePrices({
    page: 1,
    pageSize: 20,
    search: term,
    ordering: 'asset_class__name',
    filters: {
      ...(props.vertical ? { vertical: props.vertical } : {}),
      ...(props.subVertical ? { sub_vertical: props.subVertical } : {}),
    },
  })
  return data.results.map((row) => ({
    value: row.id,
    title: optionTitle(row),
    subtitle: `${row.manufacturer.name} · ${row.asset_class.name}`,
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
    @update:model-value="onPick"
  />
</template>
