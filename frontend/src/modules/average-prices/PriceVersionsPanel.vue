<script setup lang="ts">
/** Expanded grid row: every version of an average price (current included) and their average. */
import { onMounted, ref } from 'vue'
import { getAveragePriceHistory, type AveragePrice, type VersionsAverage } from './api'
import PriceVersionsList from './PriceVersionsList.vue'
import VersionsAverageCard from './VersionsAverageCard.vue'

const props = defineProps<{ row: AveragePrice }>()
const emit = defineEmits<{ open: [version: AveragePrice]; deleted: [version: AveragePrice] }>()

const versions = ref<AveragePrice[]>([])
const average = ref<VersionsAverage | null>(null)
const loading = ref(false)
const loadError = ref(false)

async function load() {
  loading.value = true
  loadError.value = false
  try {
    const history = await getAveragePriceHistory(props.row.id)
    versions.value = history.versions
    average.value = history.average
  } catch {
    loadError.value = true
  } finally {
    loading.value = false
  }
}

function onDeleted(version: AveragePrice) {
  // The grid reloads too (the current version may have changed); a row left without
  // versions leaves the grid with this panel
  load()
  emit('deleted', version)
}

onMounted(load)
</script>

<template>
  <div class="pl-12 pr-4 py-3" data-testid="versions-panel">
    <v-progress-linear v-if="loading && !versions.length" indeterminate class="my-2" />
    <v-alert v-else-if="loadError" type="error" variant="tonal" density="compact" class="my-2">
      {{ $t('common.loadError') }}
    </v-alert>
    <template v-else>
      <VersionsAverageCard
        v-if="average && average.count > 1"
        :average="average"
        :currency="row.currency"
        class="mb-2"
      />
      <div class="text-caption text-medium-emphasis">
        {{ $t('averagePrices.allVersions', versions.length) }}
      </div>
      <PriceVersionsList :versions="versions" @open="emit('open', $event)" @deleted="onDeleted" />
    </template>
  </div>
</template>
