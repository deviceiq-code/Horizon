<script setup lang="ts">
/**
 * Keywords as chips (each removable) plus an input: Enter, comma or leaving the input adds what
 * was typed. Several keywords can be pasted at once, separated by commas.
 */
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { addKeywords, MAX_KEYWORD_LENGTH, MAX_KEYWORDS } from '@/utils/keywords'

const model = defineModel<string[]>({ required: true })
withDefaults(defineProps<{ label?: string; errorMessages?: string[]; disabled?: boolean }>(), {
  label: undefined,
  errorMessages: undefined,
  disabled: false,
})

const { t } = useI18n()

const draft = ref('')
const draftError = ref('')

function add() {
  if (!draft.value.trim()) return
  const result = addKeywords(model.value, draft.value)
  if (result.error === 'tooMany') {
    draftError.value = t('keywords.tooMany', { max: MAX_KEYWORDS })
    return
  }
  if (result.error === 'tooLong') {
    draftError.value = t('validation.maxLength', { max: MAX_KEYWORD_LENGTH })
    return
  }
  model.value = result.keywords
  draft.value = ''
  draftError.value = ''
}

function onKeydown(event: KeyboardEvent) {
  if (event.key === 'Enter' || event.key === ',') {
    event.preventDefault() // Enter would submit the form; the comma is a separator
    add()
  }
}

function remove(keyword: string) {
  model.value = model.value.filter((k) => k !== keyword)
}
</script>

<template>
  <v-input :model-value="model" :error-messages="errorMessages" :disabled="disabled">
    <div class="w-100">
      <div class="text-body-2 text-medium-emphasis mb-2">{{ label ?? t('keywords.label') }}</div>
      <div class="d-flex flex-wrap align-center ga-2">
        <v-chip
          v-for="keyword in model"
          :key="keyword"
          closable
          :disabled="disabled"
          :close-label="t('keywords.remove', { keyword })"
          data-testid="keyword-chip"
          @click:close="remove(keyword)"
        >
          {{ keyword }}
        </v-chip>
        <v-text-field
          v-model="draft"
          :placeholder="t('keywords.placeholder')"
          :aria-label="t('keywords.placeholder')"
          :error-messages="draftError"
          :disabled="disabled"
          prepend-inner-icon="mdi-tag-plus-outline"
          density="compact"
          hide-details="auto"
          style="min-width: 300px; max-width: 400px"
          data-testid="keyword-input"
          @update:model-value="draftError = ''"
          @keydown="onKeydown"
          @blur="add"
        />
      </div>
    </div>
  </v-input>
</template>
