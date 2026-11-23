<script setup lang="ts">
/**
 * Photos found on the internet for the asset (SearXNG, set in Settings → System). The search
 * starts with what the form gives (manufacturer + model + asset class) and can be edited;
 * picking an image gives it back to the form, which has the server download it when saved
 * (with the page it was found on as its source).
 */
import FormDialog from '@/components/FormDialog.vue'
import { ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { ApiError } from '@/api'
import { getPhotoSuggestions, type PhotoSuggestion } from './api'

const props = defineProps<{ initialQuery: string }>()
const open = defineModel<boolean>({ required: true })
const emit = defineEmits<{ chosen: [image: string, source: string] }>()

const { t } = useI18n()

const query = ref('')
const results = ref<PhotoSuggestion[]>([])
const searching = ref(false)
const searchError = ref('')
const selected = ref<PhotoSuggestion | null>(null)
// Thumbnails that did not load are hidden
const broken = ref(new Set<string>())

function messageOf(error: unknown, fallback: string) {
  if (error instanceof ApiError && error.message) return error.message
  return fallback
}

async function search(text: string) {
  selected.value = null
  if (!text.trim()) {
    results.value = []
    return
  }
  searching.value = true
  searchError.value = ''
  try {
    const found = await getPhotoSuggestions(text)
    query.value = found.query
    results.value = found.results
    broken.value = new Set()
  } catch (error) {
    results.value = []
    searchError.value = messageOf(error, t('averagePrices.photo.searchError'))
  } finally {
    searching.value = false
  }
}

watch(
  open,
  (isOpen) => {
    if (!isOpen) return
    query.value = props.initialQuery
    results.value = []
    searchError.value = ''
    search(props.initialQuery)
  },
  { immediate: true },
)

function useSelected() {
  if (!selected.value) return
  emit('chosen', selected.value.image, selected.value.source)
  open.value = false
}

const hostOf = (url: string) => {
  try {
    return new URL(url).hostname.replace(/^www\./, '')
  } catch {
    return ''
  }
}
</script>

<template>
  <FormDialog
    v-model="open"
    :title="$t('averagePrices.photo.searchTitle')"
    icon="mdi-image-search-outline"
    max-width="980"
    @submit="search(query)"
  >
    <!-- What is searched: fixed above the results -->
    <template #header>
      <div class="d-flex ga-2 mt-4">
        <v-text-field
          v-model="query"
          :label="$t('averagePrices.photo.searchQuery')"
          prepend-inner-icon="mdi-magnify"
          density="compact"
          hide-details
          data-testid="photo-search-query"
        />
        <v-btn type="submit" color="primary" variant="tonal" :loading="searching">
          {{ $t('common.search') }}
        </v-btn>
      </div>
    </template>

    <v-progress-linear v-if="searching" indeterminate class="mb-3" />
    <v-alert v-if="searchError" type="error" variant="tonal" data-testid="photo-search-error">
      {{ searchError }}
    </v-alert>
    <p
      v-else-if="!searching && !results.length"
      class="text-medium-emphasis"
      data-testid="photo-search-empty"
    >
      {{ $t('averagePrices.photo.noResults') }}
    </p>

    <div class="results">
      <template v-for="result in results" :key="result.image">
        <button
          v-if="!broken.has(result.image)"
          type="button"
          class="result"
          :class="{ 'result--selected': selected?.image === result.image }"
          :title="result.title"
          :aria-pressed="selected?.image === result.image"
          data-testid="photo-result"
          @click="selected = result"
          @dblclick="((selected = result), useSelected())"
        >
          <img
            :src="result.thumbnail"
            :alt="result.title"
            loading="lazy"
            referrerpolicy="no-referrer"
            @error="broken = new Set(broken).add(result.image)"
          />
          <span class="result__caption text-caption text-truncate">
            {{ hostOf(result.source || result.image) }}
            <span v-if="result.resolution"> · {{ result.resolution }}</span>
          </span>
        </button>
      </template>
    </div>

    <p class="text-caption text-medium-emphasis mt-3 mb-0">
      {{ $t('averagePrices.photo.copyrightHint') }}
    </p>
    <template #actions>
      <v-btn variant="text" @click="open = false">{{ $t('common.cancel') }}</v-btn>
      <v-btn
        color="primary"
        variant="flat"
        :disabled="!selected"
        data-testid="photo-use"
        @click="useSelected"
      >
        {{ $t('averagePrices.photo.useThis') }}
      </v-btn>
    </template>
  </FormDialog>
</template>

<style scoped>
.results {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(150px, 1fr));
  gap: 12px;
}
.result {
  display: flex;
  flex-direction: column;
  padding: 6px;
  border: 2px solid transparent;
  border-radius: 8px;
  background: rgb(var(--v-theme-surface-light));
  cursor: pointer;
  text-align: left;
  min-width: 0;
}
.result:hover {
  border-color: rgba(var(--v-theme-primary), 0.4);
}
.result--selected {
  border-color: rgb(var(--v-theme-primary));
}
.result img {
  width: 100%;
  aspect-ratio: 1;
  object-fit: contain;
  background: #fff;
  border-radius: 4px;
}
.result__caption {
  margin-top: 4px;
  color: rgba(var(--v-theme-on-surface), var(--v-medium-emphasis-opacity));
}
</style>
