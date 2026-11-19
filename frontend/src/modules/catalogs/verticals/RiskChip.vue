<script setup lang="ts">
import type { Risk } from './api'

defineProps<{ risk: Risk }>()

const COLORS: Record<Risk, string> = { low: 'success', medium: 'warning', high: 'error' }
</script>

<template>
  <v-chip :color="COLORS[risk]" size="small" variant="tonal" label>
    {{ $t(`verticals.risk.${risk}`) }}
  </v-chip>
</template>
