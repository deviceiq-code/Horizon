<script setup lang="ts">
/**
 * One input per field of the sub-vertical's specification template. v-model maps the field
 * key to the text typed (numbers are converted to canonical form by the form before saving).
 */
import { useI18n } from 'vue-i18n'
import type { SpecField } from '@/modules/catalogs/asset-classes/api'
import { parseMoney } from '@/utils/money'

const values = defineModel<Record<string, string>>({ required: true })
defineProps<{ template: SpecField[]; errors?: Record<string, string[]> }>()

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
</script>

<template>
  <div>
    <p v-if="!template.length" class="text-body-2 text-medium-emphasis">
      {{ $t('averagePrices.noSpecTemplate') }}
    </p>
    <v-row dense>
      <v-col v-for="field in template" :key="field.key" cols="12" sm="6">
        <v-text-field
          v-model="values[field.key]"
          :label="field.required ? `${field.label} *` : field.label"
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
