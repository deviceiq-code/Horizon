<script setup lang="ts">
/** A person's photo in a circle (account managers, users), or their initials without one. */
import { computed } from 'vue'

const props = withDefaults(
  defineProps<{
    name: string
    /** Saved photo's address (null without one) */
    src?: string | null
    /** A picture not saved yet (e.g. chosen in a form): object URL; wins over `src` */
    previewUrl?: string | null
    size?: number
    /** Circle behind the initials (e.g. "surface" on a colored bar) */
    color?: string
  }>(),
  { src: null, previewUrl: null, size: 40, color: 'primary' },
)

const shown = computed(() => props.previewUrl || props.src)

const initials = computed(() => {
  const words = props.name.replace(/,/g, ' ').trim().split(/\s+/).filter(Boolean)
  const first = words[0]?.[0] ?? ''
  const last = words.length > 1 ? (words[words.length - 1]?.[0] ?? '') : ''
  return (first + last).toUpperCase()
})
</script>

<template>
  <v-avatar
    :size="size"
    :color="shown ? undefined : color"
    :variant="color === 'primary' ? 'tonal' : 'flat'"
    data-testid="avatar"
  >
    <v-img v-if="shown" :src="shown" :alt="name" cover data-testid="avatar-photo" />
    <span v-else :style="{ fontSize: `${Math.round(size * 0.38)}px` }">{{ initials }}</span>
  </v-avatar>
</template>
