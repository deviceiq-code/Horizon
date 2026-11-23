<script setup lang="ts">
/** A receiving lot's status as a colored chip. */
import type { LotStatus } from './api'

defineProps<{ status: LotStatus; size?: 'x-small' | 'small' | 'default' }>()

const COLORS: Record<LotStatus, string> = {
  open: 'info',
  reconciling: 'warning',
  closed: 'success',
}
</script>

<template>
  <v-chip :color="COLORS[status]" :size="size ?? 'small'" variant="tonal" label>
    {{ $t(`inventory.lots.statuses.${status}`) }}
  </v-chip>
</template>
