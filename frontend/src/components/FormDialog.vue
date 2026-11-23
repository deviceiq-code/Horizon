<script setup lang="ts">
/**
 * Every form (dialog) in three parts:
 * - header: what the form is about — icon, title, a line of basic information (e.g. the record
 *   being edited; `heading` slot to show it otherwise), on the right what matters most at a
 *   glance (`heading-end` slot, e.g. a key value) and, optionally, more in the `header` slot
 *   (fixed);
 * - body (default slot): the other controls — the only part that scrolls;
 * - footer (`actions` slot): only the form's buttons (fixed), on the right.
 * The whole dialog is a form: Enter or a submit button emits `submit`; `validate()` checks its
 * fields (exposed, as v-form's).
 */
import { ref } from 'vue'

const open = defineModel<boolean>({ required: true })
withDefaults(
  defineProps<{
    title: string
    /** Basic information under the title (e.g. the record being edited) */
    subtitle?: string | null
    icon?: string
    maxWidth?: number | string
    /** While saving: not closed by a click outside or Esc */
    persistent?: boolean
  }>(),
  { subtitle: null, icon: undefined, maxWidth: 760, persistent: false },
)
const emit = defineEmits<{ submit: [] }>()

const form = ref<{ validate: () => Promise<{ valid: boolean }> } | null>(null)
defineExpose({
  validate: () => form.value?.validate() ?? Promise.resolve({ valid: false }),
})
</script>

<template>
  <v-dialog v-model="open" :max-width="maxWidth" scrollable :persistent="persistent">
    <v-card class="form-dialog" data-testid="form-dialog">
      <v-form ref="form" class="form-dialog__form" @submit.prevent="emit('submit')">
        <!-- Header: what the form is about -->
        <header class="form-dialog__header" data-testid="form-dialog-header">
          <!-- `heading` replaces the icon, title and subtitle (e.g. with a photo) -->
          <slot v-if="$slots.heading" name="heading" />
          <div v-else class="d-flex align-center ga-3 flex-wrap">
            <v-avatar v-if="icon" color="primary" variant="tonal" rounded="lg" size="40">
              <v-icon :icon="icon" />
            </v-avatar>
            <div class="min-w-0">
              <div class="form-dialog__title" data-testid="form-dialog-title">{{ title }}</div>
              <div v-if="subtitle" class="form-dialog__subtitle text-truncate">
                {{ subtitle }}
              </div>
            </div>
            <!-- On the right: what matters most at a glance -->
            <div v-if="$slots['heading-end']" class="form-dialog__heading-end">
              <slot name="heading-end" />
            </div>
          </div>
          <slot name="header" />
        </header>
        <v-divider />
        <!-- Body: the controls (the only part that scrolls) -->
        <div class="form-dialog__body" data-testid="form-dialog-body">
          <slot />
        </div>
        <v-divider />
        <!-- Footer: only the buttons -->
        <footer class="form-dialog__footer" data-testid="form-dialog-footer">
          <slot name="actions" />
        </footer>
      </v-form>
    </v-card>
  </v-dialog>
</template>

<style scoped>
.form-dialog__form {
  display: flex;
  flex-direction: column;
  min-height: 0;
  max-height: 100%;
}
.form-dialog__header {
  flex: 0 0 auto;
  padding: 20px 24px 16px;
}
.form-dialog__title {
  font-size: 1.125rem;
  font-weight: 600;
  line-height: 1.3;
}
.form-dialog__subtitle {
  font-size: 0.875rem;
  color: rgba(var(--v-theme-on-surface), var(--v-medium-emphasis-opacity));
}
.form-dialog__body {
  flex: 1 1 auto;
  min-height: 0;
  overflow-y: auto;
  padding: 20px 24px;
}
.form-dialog__footer {
  flex: 0 0 auto;
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 8px;
  padding: 12px 24px;
}
.form-dialog__heading-end {
  margin-left: auto;
}
.min-w-0 {
  min-width: 0;
}
</style>
