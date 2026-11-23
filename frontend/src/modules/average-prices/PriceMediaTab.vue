<script setup lang="ts">
/**
 * The form's "Photo and Documents" tab: the asset's photo (a file, a search on the internet —
 * a Smart Tool of the user — or the address of an image) and its documents (button or
 * drag and drop, several at once). Every change is pending (v-model `changes`) until the form
 * is saved; they belong to the row, shared by every version. The API decides what is accepted.
 */
import { useDateFormat } from '@/composables/useDateFormat'
import { computed, onMounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { usePreferencesStore } from '@/stores/preferences'
import { formatBytes } from '@/utils/bytes'
import { listPriceDocuments, priceDocumentUrl, pricePhotoUrl, type PriceDocument } from './api'
import type { MediaChanges } from './media'
import PhotoSearchDialog from './PhotoSearchDialog.vue'
import PhotoUrlDialog from './PhotoUrlDialog.vue'

const changes = defineModel<MediaChanges>({ required: true })
const props = defineProps<{
  /** The row (any version) when it exists; null for a new price */
  rowId: number | null
  photoId: number | null
  /** Shown when there is no photo */
  icon: string
  /** Alternative text and the photo search's words ("Dell P2423H Monitor") */
  title: string
}>()

const { locale } = useI18n()
const { d } = useDateFormat()

// --- Photo ---------------------------------------------------------------------------------

const photoInput = ref<HTMLInputElement | null>(null)
const searchOpen = ref(false)
const urlOpen = ref(false)

// "Search the internet": part of the user's Internet Search (Smart Tools), with a SearXNG address
const preferences = usePreferencesStore()
const searchEnabled = computed(() => preferences.webSearch && !!preferences.searxngUrl)

/** What the photo will be once saved */
const photoShown = computed<string | null>(() => {
  const photo = changes.value.photo
  if (photo?.kind === 'file') return photo.preview
  if (photo?.kind === 'url') return photo.url
  if (photo?.kind === 'remove') return null
  return props.rowId !== null && props.photoId !== null
    ? pricePhotoUrl(props.rowId, props.photoId)
    : null
})

function setPhoto(photo: MediaChanges['photo']) {
  const previous = changes.value.photo
  if (previous?.kind === 'file') URL.revokeObjectURL(previous.preview)
  changes.value = { ...changes.value, photo }
}

function choosePhotoFile(files: FileList | null) {
  const file = files?.[0]
  if (file) setPhoto({ kind: 'file', file, preview: URL.createObjectURL(file) })
  if (photoInput.value) photoInput.value.value = ''
}

function removePhoto() {
  // A photo chosen now is just dropped; the saved one is removed when saving
  const saved = props.rowId !== null && props.photoId !== null
  setPhoto(saved ? { kind: 'remove' } : null)
}

// --- Documents -----------------------------------------------------------------------------

const documents = ref<PriceDocument[]>([])
const loadError = ref(false)
const loading = ref(false)

async function load() {
  documents.value = []
  if (props.rowId === null) return
  loading.value = true
  loadError.value = false
  try {
    documents.value = await listPriceDocuments(props.rowId)
  } catch {
    loadError.value = true
  } finally {
    loading.value = false
  }
}
onMounted(load)
watch(() => props.rowId, load)

const kept = computed(() => documents.value.filter((doc) => !changes.value.remove.includes(doc.id)))

const docInput = ref<HTMLInputElement | null>(null)
const dragging = ref(false)

function addFiles(files: FileList | File[] | null | undefined) {
  const list = [...(files ?? [])]
  if (list.length) changes.value = { ...changes.value, add: [...changes.value.add, ...list] }
  if (docInput.value) docInput.value.value = ''
}

function onDrop(event: DragEvent) {
  dragging.value = false
  addFiles(event.dataTransfer?.files)
}

function dropPending(index: number) {
  changes.value = { ...changes.value, add: changes.value.add.filter((_, i) => i !== index) }
}

function removeSaved(document: PriceDocument) {
  changes.value = { ...changes.value, remove: [...changes.value.remove, document.id] }
}

function iconFor(type: string): string {
  if (type === 'application/pdf') return 'mdi-file-pdf-box'
  if (type.startsWith('image/')) return 'mdi-file-image-outline'
  if (/sheet|excel|csv/.test(type)) return 'mdi-file-excel-outline'
  if (/presentation|powerpoint/.test(type)) return 'mdi-file-powerpoint-outline'
  if (/word|opendocument\.text|rtf/.test(type)) return 'mdi-file-word-outline'
  return 'mdi-file-document-outline'
}
const size = (bytes: number) => formatBytes(bytes, locale.value)
const href = (document: PriceDocument) =>
  props.rowId === null
    ? undefined
    : priceDocumentUrl(props.rowId, document.id, document.opens_inline)
</script>

<template>
  <div data-testid="media-tab">
    <v-alert type="info" variant="tonal" density="compact" class="mb-4" icon="mdi-layers-outline">
      {{ $t('averagePrices.media.sharedHint') }}
    </v-alert>

    <!-- Photo -->
    <div class="text-subtitle-1 mb-2">{{ $t('averagePrices.media.photo') }}</div>
    <div class="d-flex align-center ga-4 mb-6" data-testid="media-photo">
      <v-avatar v-if="photoShown" size="112" rounded="lg" class="photo-thumb">
        <!-- Never cropped: the whole photo fits -->
        <v-img
          :src="photoShown"
          :alt="title"
          width="100%"
          height="100%"
          :cover="false"
          class="pa-1"
          referrerpolicy="no-referrer"
          data-testid="media-photo-image"
        />
      </v-avatar>
      <v-avatar v-else color="primary" variant="tonal" size="112" rounded="lg">
        <v-icon :icon="icon" size="44" />
      </v-avatar>
      <div class="d-flex flex-column align-start ga-1">
        <v-menu location="bottom start">
          <template #activator="{ props: menu }">
            <v-btn
              v-bind="menu"
              variant="tonal"
              color="primary"
              :prepend-icon="photoShown ? 'mdi-camera-retake-outline' : 'mdi-camera-plus-outline'"
              data-testid="photo-upload"
            >
              {{ $t(photoShown ? 'averagePrices.photo.change' : 'averagePrices.photo.add') }}
            </v-btn>
          </template>
          <v-list density="compact">
            <v-list-item
              prepend-icon="mdi-upload-outline"
              :title="$t('averagePrices.photo.fromFile')"
              data-testid="photo-from-file"
              @click="photoInput?.click()"
            />
            <v-list-item
              v-if="searchEnabled"
              prepend-icon="mdi-image-search-outline"
              :title="$t('averagePrices.photo.fromSearch')"
              data-testid="photo-from-search"
              @click="searchOpen = true"
            />
            <v-list-item
              prepend-icon="mdi-link-variant"
              :title="$t('averagePrices.photo.fromUrl')"
              data-testid="photo-from-url"
              @click="urlOpen = true"
            />
          </v-list>
        </v-menu>
        <v-btn
          v-if="photoShown"
          variant="text"
          color="error"
          prepend-icon="mdi-trash-can-outline"
          data-testid="photo-remove"
          @click="removePhoto"
        >
          {{ $t('averagePrices.photo.remove') }}
        </v-btn>
        <v-btn
          v-if="changes.photo"
          variant="text"
          size="small"
          prepend-icon="mdi-undo"
          data-testid="photo-undo"
          @click="setPhoto(null)"
        >
          {{ $t('averagePrices.media.undo') }}
        </v-btn>
        <span v-if="changes.photo" class="text-caption text-warning" data-testid="photo-pending">
          {{ $t('averagePrices.media.pending') }}
        </span>
      </div>
      <input
        ref="photoInput"
        type="file"
        accept="image/jpeg,image/png,image/webp,image/gif"
        hidden
        data-testid="photo-input"
        @change="choosePhotoFile(($event.target as HTMLInputElement).files)"
      />
    </div>

    <!-- Documents -->
    <div class="text-subtitle-1 mb-2">{{ $t('averagePrices.media.documents') }}</div>
    <div
      class="drop-zone d-flex flex-wrap align-center ga-3 pa-4 mb-3 rounded"
      :class="{ 'drop-zone--active': dragging }"
      data-testid="documents-drop"
      @dragover.prevent="dragging = true"
      @dragleave.prevent="dragging = false"
      @drop.prevent="onDrop"
    >
      <v-icon icon="mdi-cloud-upload-outline" color="primary" />
      <span class="text-body-2 text-medium-emphasis flex-grow-1">
        {{ $t('averagePrices.documents.dropHint') }}
      </span>
      <v-btn
        color="primary"
        variant="tonal"
        prepend-icon="mdi-paperclip"
        data-testid="documents-add"
        @click="docInput?.click()"
      >
        {{ $t('averagePrices.documents.add') }}
      </v-btn>
      <input
        ref="docInput"
        type="file"
        multiple
        hidden
        data-testid="documents-input"
        @change="addFiles(($event.target as HTMLInputElement).files)"
      />
    </div>

    <v-progress-linear v-if="loading" indeterminate class="mb-2" />
    <v-alert v-else-if="loadError" type="error" variant="tonal" density="compact">
      {{ $t('common.loadError') }}
    </v-alert>
    <p v-else-if="!kept.length && !changes.add.length" class="text-medium-emphasis">
      {{ $t('averagePrices.documents.empty') }}
    </p>
    <v-list v-else density="compact" bg-color="transparent">
      <!-- To attach when saving -->
      <v-list-item
        v-for="(file, index) in changes.add"
        :key="`new-${index}-${file.name}`"
        data-testid="document-pending"
      >
        <template #prepend>
          <v-icon :icon="iconFor(file.type)" color="primary" />
        </template>
        <v-list-item-title>{{ file.name }}</v-list-item-title>
        <v-list-item-subtitle>
          {{ size(file.size) }} ·
          <span class="text-warning">{{ $t('averagePrices.media.pending') }}</span>
        </v-list-item-subtitle>
        <template #append>
          <v-btn
            icon="mdi-close"
            variant="text"
            size="small"
            :aria-label="$t('common.delete')"
            :title="$t('common.delete')"
            data-testid="document-drop-pending"
            @click="dropPending(index)"
          />
        </template>
      </v-list-item>
      <!-- Saved -->
      <v-list-item
        v-for="document in kept"
        :key="document.id"
        :href="href(document)"
        :target="document.opens_inline ? '_blank' : undefined"
        rel="noopener"
        data-testid="document-item"
      >
        <template #prepend>
          <v-icon :icon="iconFor(document.content_type)" color="primary" />
        </template>
        <v-list-item-title>{{ document.name }}</v-list-item-title>
        <v-list-item-subtitle>
          {{ size(document.size) }} · {{ d(new Date(document.uploaded_at), 'dateTime') }}
          <span v-if="document.uploaded_by_name"> · {{ document.uploaded_by_name }}</span>
        </v-list-item-subtitle>
        <template #append>
          <v-btn
            icon="mdi-delete-outline"
            variant="text"
            size="small"
            color="error"
            :aria-label="$t('common.delete')"
            :title="$t('common.delete')"
            data-testid="document-delete"
            @click.stop.prevent="removeSaved(document)"
          />
        </template>
      </v-list-item>
    </v-list>
    <p
      v-if="changes.remove.length"
      class="text-caption text-warning mt-1"
      data-testid="documents-removed"
    >
      {{ $t('averagePrices.media.removedCount', changes.remove.length) }}
      <a href="#" @click.prevent="changes = { ...changes, remove: [] }">
        {{ $t('averagePrices.media.undo') }}
      </a>
    </p>

    <PhotoSearchDialog
      v-model="searchOpen"
      :initial-query="title"
      @chosen="(url, source) => setPhoto({ kind: 'url', url, source })"
    />
    <PhotoUrlDialog
      v-model="urlOpen"
      @chosen="(url) => setPhoto({ kind: 'url', url, source: '' })"
    />
  </div>
</template>

<style scoped>
.photo-thumb {
  background: #fff;
  border: 1px solid rgba(var(--v-border-color), var(--v-border-opacity));
}
.drop-zone {
  border: 2px dashed rgba(var(--v-theme-on-surface), 0.2);
  transition:
    border-color 0.15s,
    background-color 0.15s;
}
.drop-zone--active {
  border-color: rgb(var(--v-theme-primary));
  background-color: rgba(var(--v-theme-primary), 0.06);
}
</style>
