<script setup lang="ts">
/** An inventory count's status as a colored chip. */
import type { CountStatus } from './api'

defineProps<{ status: CountStatus }>()

const COLORS: Record<CountStatus, string | undefined> = {
  counting: 'info',
  closed: 'warning',
  finished: 'success',
  cancelled: undefined,
}
</script>

<template>
  <v-chip :color="COLORS[status]" size="small" variant="tonal" label data-testid="count-status">
    {{ $t(`inventory.counts.statuses.${status}`) }}
  </v-chip>
</template>
