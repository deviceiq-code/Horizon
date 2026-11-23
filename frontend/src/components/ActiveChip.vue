<script setup lang="ts">
/** "Active" / "Inactive" status chip (customers, service providers, warehouses). */
defineProps<{ active: boolean }>()
</script>

<template>
  <v-chip :color="active ? 'success' : undefined" size="small" variant="tonal" label>
    {{ active ? $t('customers.status.active') : $t('customers.status.inactive') }}
  </v-chip>
</template>
