<script setup lang="ts">
/**
 * The asset's photo, small in the detail header (a square showing the whole photo, never
 * cropped; click to enlarge), with change/remove. Without
 * a photo it shows the asset class icon and, when editable, a button to add one. The API
 * decides what is accepted (images up to the size limit).
 */
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { ApiError, deleteErrorMessage } from '@/api'
import ConfirmDialog from '@/components/ConfirmDialog.vue'
import { useNotificationsStore } from '@/stores/notifications'
import { deletePricePhoto, pricePhotoUrl, uploadPricePhoto } from './api'

const props = defineProps<{
  /** Any version of the row */
  rowId: number
  photoId: number | null
  /** Shown when there is no photo */
  icon: string
  /** Alternative text ("Caterpillar 320 GC") */
  title: string
  canEdit: boolean
}>()
const emit = defineEmits<{ changed: [photoId: number | null] }>()

const { t } = useI18n()
const notifications = useNotificationsStore()

const fileInput = ref<HTMLInputElement | null>(null)
const busy = ref(false)
const zoomOpen = ref(false)
const confirmOpen = ref(false)

async function upload(files: FileList | null) {
  const file = files?.[0]
  if (!file) return
  busy.value = true
  try {
    const { photo_id } = await uploadPricePhoto(props.rowId, file)
    notifications.notify(t('averagePrices.photo.saved'))
    emit('changed', photo_id)
  } catch (error) {
    const messages = error instanceof ApiError ? error.fieldErrors().file : undefined
    const reason = messages?.join(' ') || (error instanceof ApiError && error.message)
    notifications.notify(reason || t('averagePrices.documents.uploadError'), 'error')
  } finally {
    busy.value = false
    if (fileInput.value) fileInput.value.value = ''
  }
}

async function remove() {
  busy.value = true
  try {
    await deletePricePhoto(props.rowId)
    notifications.notify(t('averagePrices.photo.removed'))
    emit('changed', null)
  } catch (error) {
    notifications.notify(deleteErrorMessage(error, t('common.deleteError')), 'error')
  } finally {
    busy.value = false
    confirmOpen.value = false
  }
}
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

    <div v-if="canEdit" class="d-flex">
      <v-btn
        :icon="photoId === null ? 'mdi-camera-plus-outline' : 'mdi-camera-retake-outline'"
        variant="text"
        size="x-small"
        :loading="busy"
        :aria-label="
          $t(photoId === null ? 'averagePrices.photo.add' : 'averagePrices.photo.change')
        "
        :title="$t(photoId === null ? 'averagePrices.photo.add' : 'averagePrices.photo.change')"
        data-testid="photo-upload"
        @click="fileInput?.click()"
      />
      <v-btn
        v-if="photoId !== null"
        icon="mdi-trash-can-outline"
        variant="text"
        size="x-small"
        color="error"
        :disabled="busy"
        :aria-label="$t('averagePrices.photo.remove')"
        :title="$t('averagePrices.photo.remove')"
        data-testid="photo-remove"
        @click="confirmOpen = true"
      />
      <input
        ref="fileInput"
        type="file"
        accept="image/jpeg,image/png,image/webp,image/gif"
        hidden
        data-testid="photo-input"
        @change="upload(($event.target as HTMLInputElement).files)"
      />
    </div>

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
          <v-spacer />
          <v-btn variant="text" @click="zoomOpen = false">{{ $t('common.close') }}</v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <ConfirmDialog
      v-model="confirmOpen"
      :title="$t('averagePrices.photo.remove')"
      :message="$t('averagePrices.photo.removeConfirm')"
      :confirm-text="$t('common.delete')"
      :loading="busy"
      @confirm="remove"
    />
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
