<script setup lang="ts">
/**
 * The asset's photo, small in the detail header (a square showing the whole photo, never
 * cropped; click to enlarge, with where it was found). Without a photo it shows the asset
 * class icon. Read-only: photo and documents are changed in the price's form ("Photo and
 * Documents" tab).
 */
import { ref } from 'vue'
import { pricePhotoUrl } from './api'

defineProps<{
  /** Any version of the row */
  rowId: number
  photoId: number | null
  /** Shown when there is no photo */
  icon: string
  /** Alternative text ("Caterpillar 320 GC") */
  title: string
  /** Page the photo was found on, when it came from the internet */
  sourceUrl?: string
}>()

const zoomOpen = ref(false)
</script>

<template>
  <div class="d-flex flex-column align-center ga-1" data-testid="photo">
    <v-avatar
      v-if="photoId !== null"
      size="96"
      rounded="lg"
      class="photo-thumb"
      :title="$t('averagePrices.photo.enlarge')"
      data-testid="photo-thumb"
      @click="zoomOpen = true"
    >
      <!-- Always square and never cropped: the whole photo fits, the rest is filled in
           (v-avatar makes images "cover" by default) -->
      <v-img
        :src="pricePhotoUrl(rowId, photoId)"
        :alt="title"
        width="100%"
        height="100%"
        :cover="false"
        class="photo-thumb__image"
      />
    </v-avatar>
    <v-avatar v-else color="primary" variant="tonal" size="96" rounded="lg">
      <v-icon :icon="icon" size="40" />
    </v-avatar>

    <v-dialog v-if="photoId !== null" v-model="zoomOpen" max-width="1000">
      <v-card>
        <v-img
          :src="pricePhotoUrl(rowId, photoId)"
          :alt="title"
          max-height="80vh"
          data-testid="photo-large"
        />
        <v-card-actions>
          <span class="text-body-2 text-medium-emphasis ml-2">{{ title }}</span>
          <a
            v-if="sourceUrl"
            :href="sourceUrl"
            target="_blank"
            rel="noopener noreferrer"
            class="text-body-2 ml-3"
            data-testid="photo-source"
          >
            {{ $t('averagePrices.photo.source') }}
          </a>
          <v-spacer />
          <v-btn variant="text" @click="zoomOpen = false">{{ $t('common.close') }}</v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>
  </div>
</template>

<style scoped>
.photo-thumb {
  cursor: zoom-in;
  background: #fff;
  border: 1px solid rgba(var(--v-border-color), var(--v-border-opacity));
}
.photo-thumb__image {
  padding: 4px;
}
</style>
