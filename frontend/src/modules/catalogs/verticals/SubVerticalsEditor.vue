<script setup lang="ts">
/**
 * Edit a vertical's sub-verticals: the general one (always first, cannot be renamed or removed)
 * and any number of others. New rows start with the general one's risk and terms.
 */
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { useValidationRules } from '@/composables/useValidationRules'
import { RISKS, type SubVertical } from './api'
import { keepRecommended, normalizeTerms } from './terms'

const items = defineModel<SubVertical[]>({ required: true })
const props = defineProps<{
  /** Offered in the terms field (the user may type any other number of months) */
  suggestedTerms: number[]
  maxTerm: number
  /** Field errors per row, by position */
  rowErrors: Record<number, Record<string, string[]>>
  /** Errors about the list as a whole */
  listErrors: string[]
  disabled?: boolean
}>()
const emit = defineEmits<{ edited: [index: number, field: string] }>()

const { t } = useI18n()
const rules = useValidationRules()

const riskOptions = computed(() =>
  RISKS.map((r) => ({ value: r, title: t(`verticals.risk.${r}`) })),
)

const termRules = [(v: unknown[]) => (v?.length ?? 0) > 0 || t('validation.required')]
const recommendedRules = [(v: number | null) => v !== null || t('validation.required')]

// Stable keys for rows (new rows have no id yet)
const keys = new WeakMap<SubVertical, number>()
let nextKey = 0
function keyOf(sub: SubVertical) {
  if (!keys.has(sub)) keys.set(sub, nextKey++)
  return keys.get(sub)!
}

function termOptions(sub: SubVertical) {
  return [...new Set([...props.suggestedTerms, ...sub.allowed_terms])].sort((a, b) => a - b)
}

function recommendedOptions(sub: SubVertical) {
  return sub.allowed_terms.map((n) => ({ value: n, title: t('verticals.months', n) }))
}

function setTerms(index: number, values: (string | number)[]) {
  const sub = items.value[index]!
  sub.allowed_terms = normalizeTerms(values, props.maxTerm)
  // The recommended term must stay among the allowed ones
  sub.recommended_term = keepRecommended(sub.allowed_terms, sub.recommended_term)
  emit('edited', index, 'allowed_terms')
}

function update<K extends keyof SubVertical>(index: number, field: K, value: SubVertical[K]) {
  items.value[index]![field] = value
  emit('edited', index, field)
}

function add() {
  const general = items.value.find((s) => s.is_general)
  items.value = [
    ...items.value,
    {
      name: '',
      is_general: false,
      risk: general?.risk ?? 'medium',
      allowed_terms: [...(general?.allowed_terms ?? [])],
      recommended_term: general?.recommended_term ?? null,
    },
  ]
}

function remove(index: number) {
  items.value = items.value.filter((_, i) => i !== index)
  emit('edited', index, '*')
}
</script>

<template>
  <div>
    <v-alert
      v-for="message in listErrors"
      :key="message"
      type="error"
      variant="tonal"
      density="compact"
      class="mb-3"
    >
      {{ message }}
    </v-alert>

    <v-sheet
      v-for="(sub, index) in items"
      :key="keyOf(sub)"
      border
      rounded
      class="pa-3 pb-0 mb-3"
      :data-testid="`sub-vertical-${index}`"
    >
      <v-row dense>
        <v-col cols="12" md="3">
          <v-text-field
            v-if="sub.is_general"
            :model-value="$t('verticals.general')"
            :label="$t('verticals.fields.subVertical')"
            readonly
            :hint="$t('verticals.generalHint')"
            persistent-hint
            prepend-inner-icon="mdi-lock-outline"
          />
          <v-text-field
            v-else
            :model-value="sub.name"
            :label="$t('verticals.fields.subVertical')"
            :rules="[rules.required, rules.maxLength(100)]"
            :error-messages="rowErrors[index]?.name"
            :disabled="disabled"
            maxlength="100"
            data-testid="sub-name"
            @update:model-value="update(index, 'name', $event)"
          />
        </v-col>
        <v-col cols="12" sm="4" md="2">
          <v-select
            :model-value="sub.risk"
            :items="riskOptions"
            :label="$t('verticals.fields.risk')"
            :error-messages="rowErrors[index]?.risk"
            :disabled="disabled"
            data-testid="sub-risk"
            @update:model-value="update(index, 'risk', $event)"
          />
        </v-col>
        <v-col cols="12" sm="8" md="4">
          <v-combobox
            :model-value="sub.allowed_terms"
            :items="termOptions(sub)"
            :label="$t('verticals.fields.allowedTerms')"
            :rules="termRules"
            :error-messages="rowErrors[index]?.allowed_terms"
            :disabled="disabled"
            multiple
            chips
            closable-chips
            data-testid="sub-terms"
            @update:model-value="setTerms(index, $event)"
          />
        </v-col>
        <v-col cols="10" sm="6" md="2">
          <v-select
            :model-value="sub.recommended_term"
            :items="recommendedOptions(sub)"
            :label="$t('verticals.fields.recommendedTerm')"
            :rules="recommendedRules"
            :error-messages="rowErrors[index]?.recommended_term"
            :disabled="disabled"
            data-testid="sub-recommended"
            @update:model-value="update(index, 'recommended_term', $event)"
          />
        </v-col>
        <v-col cols="2" sm="6" md="1" class="d-flex justify-end align-start pt-3">
          <v-btn
            v-if="!sub.is_general"
            icon="mdi-close"
            variant="text"
            size="small"
            :disabled="disabled"
            :aria-label="$t('verticals.removeSubVertical')"
            :title="$t('verticals.removeSubVertical')"
            data-testid="sub-remove"
            @click="remove(index)"
          />
        </v-col>
      </v-row>
    </v-sheet>

    <v-btn
      variant="tonal"
      prepend-icon="mdi-plus"
      :disabled="disabled"
      data-testid="add-sub-vertical"
      @click="add"
    >
      {{ $t('verticals.addSubVertical') }}
    </v-btn>
  </div>
</template>
