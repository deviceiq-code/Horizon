<script setup lang="ts">
/**
 * Documents of an average price (catalogs, brochures, spec sheets…), shared by every version of
 * the row: list, open and download. Read-only: they are attached and deleted in the price's
 * form ("Photo and Documents" tab).
 */
import { useDateFormat } from '@/composables/useDateFormat'
import { onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { formatBytes } from '@/utils/bytes'
import { listPriceDocuments, priceDocumentUrl, type PriceDocument } from './api'

const props = defineProps<{
  /** Any version of the row */
  rowId: number
}>()

const { locale } = useI18n()
// Dates in the formats the user chose (Settings)
const { d } = useDateFormat()

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
        </template>
      </v-list-item>
    </v-list>
  </div>
</template>
