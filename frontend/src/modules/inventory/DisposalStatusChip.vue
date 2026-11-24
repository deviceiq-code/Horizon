<script setup lang="ts">
/** A disposal's status as a colored chip. */
import type { DisposalStatus } from './api'

defineProps<{ status: DisposalStatus }>()

const COLORS: Record<DisposalStatus, string | undefined> = {
  reserved: 'warning',
  picking: 'info',
  shipped: 'success',
  cancelled: undefined,
}
</script>

<template>
  <v-chip :color="COLORS[status]" size="small" variant="tonal" label data-testid="disposal-status">
    {{ $t(`inventory.disposals.statuses.${status}`) }}
  </v-chip>
</template>
