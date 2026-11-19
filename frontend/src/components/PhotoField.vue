<script setup lang="ts">
/**
 * A person's photo in a form: circle of 96 px with "Add/Change photo" and "Remove photo". The
 * picture is cropped square and resized in the browser (utils/image.squareImage). Nothing is
 * sent here: v-model holds the pending change (a new file, 'remove' or null) for the form to
 * apply after saving the record.
 */
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import PersonAvatar from '@/components/PersonAvatar.vue'
import { useNotificationsStore } from '@/stores/notifications'
import { squareImage } from '@/utils/image'

export type PhotoChange = File | 'remove' | null

const change = defineModel<PhotoChange>({ required: true })
const props = defineProps<{
  /** For the initials */
  name: string
  /** The saved photo's address, null without one */
  currentUrl: string | null
}>()

const { t } = useI18n()
const notifications = useNotificationsStore()

const input = ref<HTMLInputElement | null>(null)
const previewUrl = ref<string | null>(null)
const preparing = ref(false)

function setPreview(file: File | null) {
  if (previewUrl.value) URL.revokeObjectURL(previewUrl.value)
  previewUrl.value = file ? URL.createObjectURL(file) : null
}

// A new form (or a cleared change) drops the preview
watch(change, (value) => {
  if (!(value instanceof File)) setPreview(null)
})
onBeforeUnmount(() => setPreview(null))

async function choose(files: FileList | null) {
  const file = files?.[0]
  if (input.value) input.value.value = ''
  if (!file) return
  if (!file.type.startsWith('image/')) {
    notifications.notify(t('photo.notImage'), 'error')
    return
  }
  preparing.value = true
  try {
    const square = await squareImage(file)
    change.value = square
    setPreview(square)
  } catch {
    notifications.notify(t('photo.notImage'), 'error')
  } finally {
    preparing.value = false
  }
}

function remove() {
  change.value = props.currentUrl ? 'remove' : null
}

const shownUrl = computed(() => (change.value === 'remove' ? null : props.currentUrl))
const hasPhoto = computed(() => change.value instanceof File || !!shownUrl.value)
</script>

<template>
  <div class="d-flex align-center ga-4" data-testid="photo">
    <PersonAvatar :name="name || '?'" :src="shownUrl" :preview-url="previewUrl" :size="96" />
    <div class="d-flex flex-column ga-1">
      <v-btn
        variant="tonal"
        size="small"
        prepend-icon="mdi-camera-outline"
        :loading="preparing"
        data-testid="photo-choose"
        @click="input?.click()"
      >
        {{ $t(hasPhoto ? 'photo.change' : 'photo.add') }}
      </v-btn>
      <v-btn
        v-if="hasPhoto"
        variant="text"
        size="small"
        color="error"
        prepend-icon="mdi-trash-can-outline"
        data-testid="photo-remove"
        @click="remove"
      >
        {{ $t('photo.remove') }}
      </v-btn>
      <input
        ref="input"
        type="file"
        accept="image/jpeg,image/png,image/webp,image/gif"
        hidden
        data-testid="photo-input"
        @change="choose(($event.target as HTMLInputElement).files)"
      />
    </div>
  </div>
</template>
