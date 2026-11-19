<script setup lang="ts">
/**
 * One 0–5 star rating in half steps. v-model is the API's decimal string ("3.5"); not filled in
 * is 0 stars. Clicking the selected star again sets it back to 0.
 */
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { numberToStars, starsToNumber } from './stars'

const model = defineModel<string>({ required: true })
withDefaults(
  defineProps<{
    label: string
    /** Meaning of the scale, e.g. "0 no demand · 5 sells easily" */
    hint?: string
    errorMessages?: string[]
    disabled?: boolean
  }>(),
  { hint: undefined, errorMessages: undefined, disabled: false },
)

const { n } = useI18n()

const stars = computed<number>({
  get: () => starsToNumber(model.value),
  set: (value) => (model.value = numberToStars(value)),
})
</script>

<template>
  <v-input
    :model-value="model"
    :error-messages="errorMessages"
    :hint="hint"
    persistent-hint
    :disabled="disabled"
  >
    <div class="d-flex flex-wrap align-center justify-space-between ga-2 w-100">
      <span class="text-body-1">{{ label }}</span>
      <div class="d-flex align-center ga-2">
        <v-rating
          v-model="stars"
          length="5"
          half-increments
          hover
          clearable
          density="comfortable"
          color="grey-lighten-1"
          active-color="amber-darken-2"
          :disabled="disabled"
          :aria-label="label"
          data-testid="stars"
        />
        <span
          class="text-body-2 font-weight-medium text-no-wrap"
          style="min-width: 56px"
          data-testid="stars-value"
        >
          {{ n(stars, 'rating') }} / 5
        </span>
      </div>
    </div>
  </v-input>
</template>
