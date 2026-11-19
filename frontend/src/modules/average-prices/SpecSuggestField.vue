<script setup lang="ts">
/**
 * Text specification field that offers values already used in other prices of the same asset
 * class (most used first, searched by the API as you type). Any new value can still be typed.
 */
import { onBeforeUnmount, ref } from 'vue'
import { getSpecSuggestions } from './api'

const value = defineModel<string>({ default: '' })
const props = defineProps<{ assetClassId: number; fieldKey: string }>()

const DEBOUNCE_MS = 250

const items = ref<string[]>([])
const loading = ref(false)
let timer: ReturnType<typeof setTimeout> | undefined
let requestId = 0

async function fetchSuggestions(search: string) {
  const mine = ++requestId
  loading.value = true
  try {
    const found = await getSpecSuggestions(props.assetClassId, props.fieldKey, search)
    if (mine === requestId) items.value = found
  } catch {
    if (mine === requestId) items.value = []
  } finally {
    if (mine === requestId) loading.value = false
  }
}

function onSearch(search: string | null) {
  clearTimeout(timer)
  timer = setTimeout(() => fetchSuggestions(search?.trim() ?? ''), DEBOUNCE_MS)
}

onBeforeUnmount(() => clearTimeout(timer))
</script>

<template>
  <v-combobox
    :model-value="value"
    :items="items"
    :loading="loading"
    no-filter
    hide-no-data
    :menu-icon="''"
    autocomplete="off"
    @update:model-value="value = $event ?? ''"
    @update:search="onSearch"
    @focus="fetchSuggestions(value?.trim() ?? '')"
  />
</template>
