<script setup lang="ts">
/** A location's kind of area, with its icon. */
import type { AreaType } from './api'

defineProps<{ area: AreaType; size?: 'x-small' | 'small' }>()

const ICONS: Record<AreaType, string> = {
  dock: 'mdi-truck-delivery-outline',
  inspection_queue: 'mdi-tray-full',
  bench: 'mdi-desk',
  quarantine: 'mdi-shield-lock-outline',
  stock: 'mdi-warehouse',
  scrap: 'mdi-recycle',
  shipping: 'mdi-truck-fast-outline',
  virtual_transit: 'mdi-transit-transfer',
}
</script>

<template>
  <v-chip :prepend-icon="ICONS[area]" :size="size ?? 'small'" variant="outlined" label>
    {{ $t(`inventory.areas.${area}`) }}
  </v-chip>
</template>
