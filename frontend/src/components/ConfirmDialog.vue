<script setup lang="ts">
/** Generic confirmation dialog (e.g. before deleting a record). */
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
  <v-dialog v-model="open" max-width="440" :persistent="loading">
    <v-card :title="title">
      <v-card-text>{{ message }}</v-card-text>
      <v-card-actions>
        <v-spacer />
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
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>
