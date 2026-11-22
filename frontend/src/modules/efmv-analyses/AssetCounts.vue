<script setup lang="ts">
/**
 * How many units of each kind a scenario has, by quantity: HW (assets), SW (to come) and SV
 * (services).
 */
defineProps<{ counts: { hw: number; sw: number; sv: number } }>()

const KINDS = [
  { key: 'hw', color: 'primary' },
  { key: 'sw', color: 'info' },
  { key: 'sv', color: 'warning' },
] as const
</script>

<template>
  <span class="d-inline-flex ga-1 align-center" data-testid="asset-counts">
    <v-chip
      v-for="kind in KINDS"
      :key="kind.key"
      size="x-small"
      variant="tonal"
      label
      :color="counts[kind.key] ? kind.color : undefined"
      :title="$t(`efmv.totals.${kind.key}Hint`)"
      :data-testid="`asset-count-${kind.key}`"
    >
      {{ $t(`efmv.totals.${kind.key}`) }} {{ counts[kind.key] }}
    </v-chip>
  </span>
</template>
