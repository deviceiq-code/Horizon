<script setup lang="ts">
/**
 * Documents of an average price (catalogs, brochures, spec sheets…), shared by every version of
 * the row: list, upload (button or drag and drop, several files at once), open/download and
 * delete. What is accepted (type, size) is decided by the API; its messages are shown per file.
 */
import { onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { ApiError, deleteErrorMessage } from '@/api'
import ConfirmDialog from '@/components/ConfirmDialog.vue'
import { useNotificationsStore } from '@/stores/notifications'
import { formatBytes } from '@/utils/bytes'
import {
  deletePriceDocument,
  listPriceDocuments,
  priceDocumentUrl,
  uploadPriceDocument,
  type PriceDocument,
} from './api'

const props = defineProps<{
  /** Any version of the row */
  rowId: number
  /** False for a deleted price (documents can still be opened) */
  canEdit: boolean
}>()
const emit = defineEmits<{ changed: [count: number] }>()

const { t, locale, d } = useI18n()
const notifications = useNotificationsStore()

const documents = ref<PriceDocument[]>([])
const loading = ref(false)
const loadError = ref(false)

async function load() {
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

// --- Upload ----------------------------------------------------------------------------------

const fileInput = ref<HTMLInputElement | null>(null)
const uploading = ref<string | null>(null)
const dragging = ref(false)

function uploadError(error: unknown): string {
  if (error instanceof ApiError) {
    const messages = error.fieldErrors().file
    if (messages?.length) return messages.join(' ')
    if (error.message) return error.message
  }
  return t('averagePrices.documents.uploadError')
}

async function upload(files: FileList | File[] | null | undefined) {
  const list = [...(files ?? [])]
  if (!list.length || uploading.value) return
  let added = 0
  for (const file of list) {
    uploading.value = file.name
    try {
      await uploadPriceDocument(props.rowId, file)
      added += 1
    } catch (error) {
      notifications.notify(`${file.name}: ${uploadError(error)}`, 'error')
    }
  }
  uploading.value = null
  if (fileInput.value) fileInput.value.value = ''
  if (added) {
    notifications.notify(t('averagePrices.documents.uploaded', added))
    await load()
    emit('changed', documents.value.length)
  }
}

function onDrop(event: DragEvent) {
  dragging.value = false
  if (props.canEdit) upload(event.dataTransfer?.files)
}

// --- Delete ----------------------------------------------------------------------------------

const deleting = ref<PriceDocument | null>(null)
const confirmOpen = ref(false)
const deleteInProgress = ref(false)

function askDelete(document: PriceDocument) {
  deleting.value = document
  confirmOpen.value = true
}

async function confirmDelete() {
  if (!deleting.value) return
  deleteInProgress.value = true
  try {
    await deletePriceDocument(props.rowId, deleting.value.id)
    notifications.notify(t('averagePrices.documents.deleted'))
    await load()
    emit('changed', documents.value.length)
  } catch (error) {
    notifications.notify(deleteErrorMessage(error, t('common.deleteError')), 'error')
  } finally {
    confirmOpen.value = false
    deleteInProgress.value = false
  }
}

// --- Display ---------------------------------------------------------------------------------

function iconFor(document: PriceDocument): string {
  const type = document.content_type
  if (type === 'application/pdf') return 'mdi-file-pdf-box'
  if (type.startsWith('image/')) return 'mdi-file-image-outline'
  if (/sheet|excel|csv/.test(type)) return 'mdi-file-excel-outline'
  if (/presentation|powerpoint/.test(type)) return 'mdi-file-powerpoint-outline'
  if (/word|opendocument\.text|rtf/.test(type)) return 'mdi-file-word-outline'
  return 'mdi-file-document-outline'
}

const size = (document: PriceDocument) => formatBytes(document.size, locale.value)
const dateTime = (value: string) => d(new Date(value), 'dateTime')
const href = (document: PriceDocument, inline = false) =>
  priceDocumentUrl(props.rowId, document.id, inline)
</script>

<template>
  <div data-testid="documents">
    <div
      v-if="canEdit"
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
        :loading="!!uploading"
        data-testid="documents-add"
        @click="fileInput?.click()"
      >
        {{ $t('averagePrices.documents.add') }}
      </v-btn>
      <input
        ref="fileInput"
        type="file"
        multiple
        hidden
        data-testid="documents-input"
        @change="upload(($event.target as HTMLInputElement).files)"
      />
    </div>
    <p v-if="uploading" class="text-caption text-medium-emphasis mb-2">
      {{ $t('averagePrices.documents.uploading', { name: uploading }) }}
    </p>

    <v-progress-linear v-if="loading && !documents.length" indeterminate class="mb-2" />
    <v-alert v-else-if="loadError" type="error" variant="tonal" density="compact">
      {{ $t('common.loadError') }}
    </v-alert>
    <p v-else-if="!documents.length" class="text-medium-emphasis">
      {{ $t('averagePrices.documents.empty') }}
    </p>
    <v-list v-else density="compact" bg-color="transparent">
      <v-list-item
        v-for="document in documents"
        :key="document.id"
        :href="href(document, document.opens_inline)"
        :target="document.opens_inline ? '_blank' : undefined"
        rel="noopener"
        data-testid="document-item"
      >
        <template #prepend>
          <v-icon :icon="iconFor(document)" color="primary" />
        </template>
        <v-list-item-title>{{ document.name }}</v-list-item-title>
        <v-list-item-subtitle>
          {{ size(document) }} · {{ dateTime(document.uploaded_at) }}
          <span v-if="document.uploaded_by_name"> · {{ document.uploaded_by_name }}</span>
        </v-list-item-subtitle>
        <template #append>
          <v-btn
            icon="mdi-download-outline"
            variant="text"
            size="small"
            :href="href(document)"
            :aria-label="$t('averagePrices.documents.download')"
            :title="$t('averagePrices.documents.download')"
            data-testid="document-download"
            @click.stop
          />
          <v-btn
            v-if="canEdit"
            icon="mdi-delete-outline"
            variant="text"
            size="small"
            color="error"
            :aria-label="$t('common.delete')"
            :title="$t('common.delete')"
            data-testid="document-delete"
            @click.stop.prevent="askDelete(document)"
          />
        </template>
      </v-list-item>
    </v-list>

    <ConfirmDialog
      v-model="confirmOpen"
      :title="$t('averagePrices.documents.deleteTitle')"
      :message="
        deleting ? $t('averagePrices.documents.deleteConfirm', { name: deleting.name }) : ''
      "
      :confirm-text="$t('common.delete')"
      :loading="deleteInProgress"
      @confirm="confirmDelete"
    />
  </div>
</template>

<style scoped>
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
