<script setup lang="ts">
/**
 * List of terms in months, always visible as chips. Each chip can be removed; "Add term"
 * opens a small input to type a number of months (Enter adds, Esc cancels, leaving adds).
 * Takes part in v-form validation (at least one term) through v-input.
 */
import { nextTick, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { parseTerm } from './terms'

const model = defineModel<number[]>({ required: true })
const props = withDefaults(
  defineProps<{
    label: string
    /** Longest term accepted, in months */
    max: number
    errorMessages?: string[]
    disabled?: boolean
  }>(),
  { errorMessages: undefined, disabled: false },
)

const { t } = useI18n()

const rules = [(v: number[]) => (v?.length ?? 0) > 0 || t('validation.required')]

const adding = ref(false)
const draft = ref('')
const draftError = ref('')
const inputRef = ref<{ focus: () => void } | null>(null)

async function startAdding() {
  adding.value = true
  draft.value = ''
  draftError.value = ''
  await nextTick()
  inputRef.value?.focus()
}

function stopAdding() {
  adding.value = false
  draft.value = ''
  draftError.value = ''
}

/** Add the typed term. Empty input just closes it; invalid input stays open with a message. */
function confirm() {
  if (!draft.value.trim()) {
    stopAdding()
    return
  }
  const term = parseTerm(draft.value, props.max)
  if (term === null) {
    draftError.value = t('verticals.terms.invalid', { max: props.max })
    return
  }
  if (model.value.includes(term)) {
    draftError.value = t('verticals.terms.duplicate')
    return
  }
  model.value = [...model.value, term].sort((a, b) => a - b)
  stopAdding()
}

function remove(term: number) {
  model.value = model.value.filter((m) => m !== term)
}
</script>

<template>
  <v-input :model-value="model" :rules="rules" :error-messages="errorMessages" :disabled="disabled">
    <div class="w-100">
      <div class="text-body-2 text-medium-emphasis mb-2">{{ label }}</div>
      <div class="d-flex flex-wrap align-center ga-2" style="min-height: 40px">
        <v-chip
          v-for="term in model"
          :key="term"
          closable
          :disabled="disabled"
          :close-label="t('verticals.terms.remove', { n: term })"
          data-testid="term-chip"
          @click:close="remove(term)"
        >
          {{ term }}
        </v-chip>

        <v-text-field
          v-if="adding"
          ref="inputRef"
          v-model="draft"
          type="number"
          inputmode="numeric"
          min="1"
          :max="max"
          :suffix="t('verticals.terms.monthsSuffix')"
          :error-messages="draftError"
          :aria-label="t('verticals.terms.add')"
          density="compact"
          hide-details="auto"
          style="max-width: 170px"
          data-testid="term-input"
          @update:model-value="draftError = ''"
          @keydown.enter.prevent="confirm"
          @keydown.esc.prevent.stop="stopAdding"
          @blur="confirm"
        />
        <v-btn
          v-else
          size="small"
          variant="tonal"
          prepend-icon="mdi-plus"
          :disabled="disabled"
          data-testid="term-add"
          @click="startAdding"
        >
          {{ t('verticals.terms.add') }}
        </v-btn>
      </div>
    </div>
  </v-input>
</template>
