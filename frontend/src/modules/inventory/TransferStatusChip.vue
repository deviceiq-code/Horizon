<script setup lang="ts">
/** A transfer's status as a colored chip (late while in transit: how many days). */
import type { TransferStatus } from './api'

defineProps<{ status: TransferStatus; daysLate?: number }>()

const COLORS: Record<TransferStatus, string | undefined> = {
  requested: 'warning',
  approved: 'info',
  picking: 'info',
  in_transit: 'primary',
  received: 'success',
  received_with_discrepancy: 'error',
  cancelled: undefined,
}
</script>

<template>
  <span class="d-inline-flex align-center ga-1">
    <v-chip
      :color="COLORS[status]"
      size="small"
      variant="tonal"
      label
      data-testid="transfer-status"
    >
      {{ $t(`inventory.transfers.statuses.${status}`) }}
    </v-chip>
    <v-chip
      v-if="daysLate"
      color="error"
      size="x-small"
      label
      prepend-icon="mdi-clock-alert-outline"
      data-testid="transfer-late"
    >
      {{ $t('inventory.transfers.late', daysLate) }}
    </v-chip>
  </span>
</template>
