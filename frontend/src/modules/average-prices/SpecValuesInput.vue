<script setup lang="ts">
/**
 * One input per field of the asset class's specification template. v-model maps the field
 * key to its value as text (numbers are converted to canonical form by the form before
 * saving): text (with suggestions from other prices of the same asset class), number, yes/no
 * ("true"/"false"), an item of the field's list, or a 0–5 star rating ("3.5"; "" = not rated).
 */
import { useI18n } from 'vue-i18n'
import type { SpecField } from '@/modules/catalogs/asset-classes/api'
import StarRatingInput from '@/modules/catalogs/remarketing/StarRatingInput.vue'
import { parseMoney } from '@/utils/money'
import SpecSuggestField from './SpecSuggestField.vue'

const values = defineModel<Record<string, string>>({ required: true })
defineProps<{
  template: SpecField[]
  /** Asset class the suggestions come from */
  assetClassId: number | null
  errors?: Record<string, string[]>
}>()

const { t, locale } = useI18n()

function rulesFor(field: SpecField) {
  return [
    (v: string) => !field.required || !!v?.trim() || t('validation.required'),
    (v: string) =>
      field.kind !== 'number' ||
      !v?.trim() ||
      parseMoney(v, locale.value, 6) !== null ||
      t('validation.number'),
  ]
}

const labelOf = (field: SpecField) => (field.required ? `${field.label} *` : field.label)

// Stars: 0 means "not rated" (stored as "")
const starsOf = (field: SpecField) => values.value[field.key] || '0.0'
function setStars(field: SpecField, stars: string) {
  values.value[field.key] = Number(stars) === 0 ? '' : stars
}

// Yes/no: clicking the chosen answer again clears it (when the field is optional)
function setAnswer(field: SpecField, answer: string | undefined) {
  values.value[field.key] = answer ?? ''
}
</script>

<template>
  <div>
    <p v-if="!template.length" class="text-body-2 text-medium-emphasis">
      {{ $t('averagePrices.noSpecTemplate') }}
    </p>
    <v-row dense>
      <v-col v-for="field in template" :key="field.key" cols="12" sm="6">
        <SpecSuggestField
          v-if="field.kind === 'text' && assetClassId !== null"
          v-model="values[field.key]"
          :asset-class-id="assetClassId"
          :field-key="field.key"
          :label="labelOf(field)"
          :rules="rulesFor(field)"
          :error-messages="errors?.[field.key]"
          maxlength="200"
          :data-testid="`spec-${field.key}`"
        />
        <v-input
          v-else-if="field.kind === 'boolean'"
          :model-value="values[field.key]"
          :rules="rulesFor(field)"
          :error-messages="errors?.[field.key]"
          :data-testid="`spec-${field.key}`"
        >
          <div class="d-flex align-center justify-space-between ga-3 w-100">
            <span class="text-body-1">{{ labelOf(field) }}</span>
            <v-btn-toggle
              :model-value="values[field.key] || undefined"
              :mandatory="false"
              divided
              density="compact"
              variant="outlined"
              color="primary"
              @update:model-value="setAnswer(field, $event)"
            >
              <v-btn value="true" size="small" data-testid="answer-yes">
                {{ $t('common.yes') }}
              </v-btn>
              <v-btn value="false" size="small" data-testid="answer-no">
                {{ $t('common.no') }}
              </v-btn>
            </v-btn-toggle>
          </div>
        </v-input>
        <v-select
          v-else-if="field.kind === 'choice'"
          v-model="values[field.key]"
          :items="field.options"
          :label="labelOf(field)"
          :rules="rulesFor(field)"
          :error-messages="errors?.[field.key]"
          :clearable="!field.required"
          :data-testid="`spec-${field.key}`"
        />
        <StarRatingInput
          v-else-if="field.kind === 'rating'"
          :model-value="starsOf(field)"
          :label="labelOf(field)"
          :rules="field.required ? [() => !!values[field.key] || t('validation.required')] : []"
          :error-messages="errors?.[field.key]"
          :data-testid="`spec-${field.key}`"
          @update:model-value="setStars(field, $event)"
        />
        <v-text-field
          v-else
          v-model="values[field.key]"
          :label="labelOf(field)"
          :suffix="field.unit || undefined"
          :inputmode="field.kind === 'number' ? 'decimal' : undefined"
          :rules="rulesFor(field)"
          :error-messages="errors?.[field.key]"
          maxlength="200"
          :data-testid="`spec-${field.key}`"
        />
      </v-col>
    </v-row>
  </div>
</template>
