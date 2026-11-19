<script setup lang="ts" generic="F extends string">
/**
 * Edit a remarketing rating: one star input per field (labels and hints from
 * `<i18nPrefix>.<field>.label|hint`) and the live average below. `ratings` is the form object
 * holding the fields; it is edited in place.
 */
import { computed } from 'vue'
import RemarketingAverage from './RemarketingAverage.vue'
import StarRatingInput from './StarRatingInput.vue'
import { previewAverage } from './stars'

const props = defineProps<{
  ratings: Record<F, string>
  fields: readonly F[]
  i18nPrefix: string
  errors?: Record<string, string[]>
}>()
const emit = defineEmits<{ edited: [field: F] }>()

const average = computed(() => previewAverage(props.fields.map((f) => props.ratings[f])))

function update(field: F, value: string) {
  // eslint-disable-next-line vue/no-mutating-props -- the parent passes its form object
  props.ratings[field] = value
  emit('edited', field)
}
</script>

<template>
  <v-sheet border rounded class="px-4 pt-3 pb-2">
    <StarRatingInput
      v-for="field in fields"
      :key="field"
      :model-value="ratings[field]"
      :label="$t(`${i18nPrefix}.${field}.label`)"
      :hint="$t(`${i18nPrefix}.${field}.hint`)"
      :error-messages="errors?.[field]"
      class="mb-2"
      :data-testid="`rating-${field}`"
      @update:model-value="update(field, $event)"
    />
    <v-divider class="my-2" />
    <div class="d-flex flex-wrap align-center justify-space-between ga-2 py-1">
      <span class="text-body-1 font-weight-medium">{{ $t('catalogs.remarketing.average') }}</span>
      <span data-testid="average-preview">
        <RemarketingAverage :average="average" size="default" />
      </span>
    </div>
  </v-sheet>
</template>
