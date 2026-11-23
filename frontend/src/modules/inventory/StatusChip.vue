<script setup lang="ts">
/** An asset's status as a colored chip (held for a dispute: a lock beside it). */
import type { AssetStatus } from './api'

defineProps<{ status: AssetStatus; held?: boolean; size?: 'x-small' | 'small' | 'default' }>()

const COLORS: Record<AssetStatus, string | undefined> = {
  in_triage: 'info',
  awaiting_inspection: 'info',
  in_inspection: 'primary',
  blocked: 'error',
  available: 'success',
  reserved: 'warning',
  scrap: undefined,
  in_transit: 'secondary',
  written_off: undefined,
}
</script>

<template>
  <v-chip
    :color="COLORS[status]"
    :size="size ?? 'small'"
    :prepend-icon="held ? 'mdi-lock-outline' : undefined"
    :title="held ? $t('inventory.heldForDispute') : undefined"
    variant="tonal"
    label
    data-testid="status-chip"
  >
    {{ $t(`inventory.statuses.${status}`) }}
  </v-chip>
</template>
