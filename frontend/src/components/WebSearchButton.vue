<script setup lang="ts">
/**
 * Inside a text field, on the right (`#append-inner`): opens an Internet search for what was
 * typed in a new browser tab, with the user's search engine (Settings → Smart Tools).
 * Disabled while the field is empty; out of the Tab order (the form's fields come first).
 */
import { computed } from 'vue'
import { usePreferencesStore } from '@/stores/preferences'
import { WEB_SEARCH_ENGINES, webSearchUrl } from '@/webSearch'

const props = defineProps<{ term: string | null | undefined }>()
const preferences = usePreferencesStore()

const url = computed(() => webSearchUrl(preferences.webSearchEngine, props.term ?? ''))
const engine = computed(() => WEB_SEARCH_ENGINES[preferences.webSearchEngine].name)

function search() {
  if (url.value) window.open(url.value, '_blank', 'noopener,noreferrer')
}
</script>

<template>
  <v-btn
    icon="mdi-web"
    variant="text"
    size="small"
    density="comfortable"
    :disabled="!url"
    tabindex="-1"
    :title="$t('webSearch.button', { engine })"
    :aria-label="$t('webSearch.button', { engine })"
    data-testid="web-search"
    @click.stop="search"
    @mousedown.prevent
  />
</template>
