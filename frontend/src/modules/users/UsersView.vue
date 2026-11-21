<script setup lang="ts">
/** Users of the system (administrators only). Their roles are on the Roles page. */
import UsersTab from './UsersTab.vue'
</script>

<template>
  <v-container fluid class="module-page">
    <h1 class="mb-1">{{ $t('users.title') }}</h1>
    <p class="text-medium-emphasis mb-4">{{ $t('users.subtitle') }}</p>
    <UsersTab />
  </v-container>
</template>
