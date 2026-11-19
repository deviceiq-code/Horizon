<script setup lang="ts">
/**
 * The remarketing average: stars plus the number (e.g. ★★★☆☆ 3,1 / 5). `average` is the API's
 * decimal string ("3.13") or a live preview number. With `breakdown`, hovering shows each rating.
 */
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

const props = withDefaults(
  defineProps<{
    average: string | number
    /** Individual ratings shown on hover: label and decimal string */
    breakdown?: { label: string; value: string }[]
    size?: 'x-small' | 'small' | 'default'
  }>(),
  { breakdown: () => [], size: 'small' },
)

const { n } = useI18n()

// Number() only to draw stars / format for display; the value itself comes from the API
const value = computed(() => Number(props.average))
</script>

<template>
  <v-tooltip :disabled="!breakdown.length" location="top">
    <template #activator="{ props: tooltip }">
      <span
        v-bind="tooltip"
        class="d-inline-flex align-center ga-1 text-no-wrap"
        data-testid="remarketing-average"
      >
        <!-- Decorative: the number next to it says the same (and screen readers read that) -->
        <v-rating
          aria-hidden="true"
          :model-value="value"
          length="5"
          half-increments
          readonly
          density="compact"
          :size="size"
          color="grey-lighten-1"
          active-color="amber-darken-2"
        />
        <span class="font-weight-medium">{{ n(value, 'rating') }}</span>
        <span class="text-medium-emphasis">/ 5</span>
      </span>
    </template>
    <div v-for="item in breakdown" :key="item.label" class="d-flex justify-space-between ga-4">
      <span>{{ item.label }}</span>
      <span class="font-weight-medium">{{ n(Number(item.value), 'rating') }}</span>
    </div>
  </v-tooltip>
</template>
