<script setup lang="ts">
/**
 * The address of an image on the internet as the photo: given back to the form, which has the
 * server download it when saved (the server checks the address and the image then).
 */
import FormDialog from '@/components/FormDialog.vue'
import { ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'

const open = defineModel<boolean>({ required: true })
const emit = defineEmits<{ chosen: [url: string] }>()

const { t } = useI18n()

const url = ref('')
const errors = ref<string[]>([])

watch(open, (isOpen) => {
  if (!isOpen) return
  url.value = ''
  errors.value = []
})

function isWebAddress(text: string) {
  try {
    return ['http:', 'https:'].includes(new URL(text).protocol)
  } catch {
    return false
  }
}

function save() {
  const address = url.value.trim()
  if (!isWebAddress(address)) {
    errors.value = [t('averagePrices.photo.invalidUrl')]
    return
  }
  emit('chosen', address)
  open.value = false
}
</script>

<template>
  <FormDialog
    v-model="open"
    :title="$t('averagePrices.photo.fromUrlTitle')"
    icon="mdi-link-variant"
    max-width="560"
    @submit="save"
  >
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

    <template #actions>
      <v-btn variant="text" @click="open = false">{{ $t('common.cancel') }}</v-btn>
      <v-btn
        type="submit"
        color="primary"
        variant="flat"
        :disabled="!url.trim()"
        data-testid="photo-url-save"
      >
        {{ $t('averagePrices.photo.useThis') }}
      </v-btn>
    </template>
  </FormDialog>
</template>
