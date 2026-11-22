<script setup lang="ts">
/** Generic confirmation dialog (e.g. before deleting a record). */
import FormDialog from '@/components/FormDialog.vue'
withDefaults(
  defineProps<{
    title: string
    message: string
    confirmText: string
    confirmColor?: string
    loading?: boolean
  }>(),
  { confirmColor: 'error', loading: false },
)

const open = defineModel<boolean>({ required: true })
const emit = defineEmits<{ confirm: [] }>()
</script>

<template>
  <FormDialog
    v-model="open"
    :title="title"
    :icon="confirmColor === 'error' ? 'mdi-alert-circle-outline' : 'mdi-help-circle-outline'"
    max-width="460"
    :persistent="loading"
  >
    {{ message }}
    <template #actions>
      <v-btn variant="text" :disabled="loading" @click="open = false">
        {{ $t('common.cancel') }}
      </v-btn>
      <v-btn
        :color="confirmColor"
        variant="flat"
        :loading="loading"
        data-testid="confirm-button"
        @click="emit('confirm')"
      >
        {{ confirmText }}
      </v-btn>
    </template>
  </FormDialog>
</template>
