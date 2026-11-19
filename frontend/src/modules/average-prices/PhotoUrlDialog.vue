<script setup lang="ts">
/** Set the photo from the address of an image on the internet (the server downloads it). */
import { ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { ApiError } from '@/api'
import { setPhotoFromUrl } from './api'

const props = defineProps<{ rowId: number }>()
const open = defineModel<boolean>({ required: true })
const emit = defineEmits<{ chosen: [photoId: number] }>()

const { t } = useI18n()

const url = ref('')
const errors = ref<string[]>([])
const saving = ref(false)

watch(open, (isOpen) => {
  if (!isOpen) return
  url.value = ''
  errors.value = []
})

async function save() {
  saving.value = true
  errors.value = []
  try {
    const { photo_id } = await setPhotoFromUrl(props.rowId, url.value.trim())
    emit('chosen', photo_id)
    open.value = false
  } catch (error) {
    const messages = error instanceof ApiError ? error.fieldErrors().url : undefined
    errors.value = [
      messages?.join(' ') ||
        (error instanceof ApiError && error.message) ||
        t('averagePrices.photo.downloadError'),
    ]
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <v-dialog v-model="open" max-width="560">
    <v-card :title="$t('averagePrices.photo.fromUrlTitle')">
      <v-form @submit.prevent="save">
        <v-card-text>
          <p class="text-body-2 text-medium-emphasis mb-3">
            {{ $t('averagePrices.photo.fromUrlHint') }}
          </p>
          <v-text-field
            v-model="url"
            :label="$t('averagePrices.photo.imageUrl')"
            placeholder="https://…/photo.jpg"
            prepend-inner-icon="mdi-link-variant"
            :error-messages="errors"
            autofocus
            data-testid="photo-url"
            @update:model-value="errors = []"
          />
        </v-card-text>
        <v-card-actions>
          <v-spacer />
          <v-btn variant="text" @click="open = false">{{ $t('common.cancel') }}</v-btn>
          <v-btn
            type="submit"
            color="primary"
            variant="flat"
            :disabled="!url.trim()"
            :loading="saving"
            data-testid="photo-url-save"
          >
            {{ $t('averagePrices.photo.useThis') }}
          </v-btn>
        </v-card-actions>
      </v-form>
    </v-card>
  </v-dialog>
</template>
