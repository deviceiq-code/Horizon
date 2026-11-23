<script setup lang="ts">
/** An appointment's status as a colored chip. */
import type { AppointmentStatus } from './api'

defineProps<{ status: AppointmentStatus; size?: 'x-small' | 'small' }>()

const COLORS: Record<AppointmentStatus, string | undefined> = {
  scheduled: 'info',
  confirmed: 'primary',
  in_progress: 'warning',
  done: 'success',
  cancelled: undefined,
  no_show: 'error',
}
</script>

<template>
  <v-chip :color="COLORS[status]" :size="size ?? 'small'" variant="tonal" label>
    {{ $t(`inventory.appointments.statuses.${status}`) }}
  </v-chip>
</template>
