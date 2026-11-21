<script setup lang="ts">
/** Roles of the users (administrators only); system roles show translated. */
import RolesTab from './RolesTab.vue'
</script>

<template>
  <v-container fluid class="module-page">
    <h1 class="mb-1">{{ $t('users.tabs.roles') }}</h1>
    <p class="text-medium-emphasis mb-4">{{ $t('users.rolesSubtitle') }}</p>
    <RolesTab />
  </v-container>
</template>
