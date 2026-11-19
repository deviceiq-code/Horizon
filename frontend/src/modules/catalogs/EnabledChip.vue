<script setup lang="ts">
/** "Enabled" / "Disabled" status chip used by the catalog grids. */
defineProps<{ enabled: boolean }>()
</script>

<template>
  <v-chip :color="enabled ? 'success' : undefined" size="small" variant="tonal" label>
    {{ enabled ? $t('catalogs.status.enabled') : $t('catalogs.status.disabled') }}
  </v-chip>
</template>
