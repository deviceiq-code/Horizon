<script setup lang="ts">
/** An account manager's photo in a circle, or their initials without one. */
import { computed } from 'vue'
import { accountManagerPhotoUrl } from './api'

const props = withDefaults(
  defineProps<{
    name: string
    /** Saved photo: the manager's id and photo version */
    id?: number | null
    photoVersion?: string | null
    /** A picture not saved yet (e.g. chosen in the form): object URL */
    previewUrl?: string | null
    size?: number
  }>(),
  { id: null, photoVersion: null, previewUrl: null, size: 40 },
)

const src = computed(() => {
  if (props.previewUrl) return props.previewUrl
  if (props.id !== null && props.photoVersion) {
    return accountManagerPhotoUrl(props.id, props.photoVersion)
  }
  return null
})

const initials = computed(() => {
  const words = props.name.trim().split(/\s+/).filter(Boolean)
  const first = words[0]?.[0] ?? ''
  const last = words.length > 1 ? (words[words.length - 1]?.[0] ?? '') : ''
  return (first + last).toUpperCase()
})
</script>

<template>
  <v-avatar :size="size" :color="src ? undefined : 'primary'" variant="tonal" data-testid="avatar">
    <v-img v-if="src" :src="src" :alt="name" cover data-testid="avatar-photo" />
    <span v-else :style="{ fontSize: `${Math.round(size * 0.38)}px` }">{{ initials }}</span>
  </v-avatar>
</template>
