<script setup lang="ts">
/** Global settings (Administration → System Settings): one card per setting. */
import SystemSettingsCard from '@/components/SystemSettingsCard.vue'
import UserNameDisplayCard from '@/components/UserNameDisplayCard.vue'
</script>

<template>
  <v-container style="max-width: 900px">
    <h1 class="text-h5 mb-1">{{ $t('settings.tabs.system') }}</h1>
    <p class="text-medium-emphasis mb-6">{{ $t('system.subtitle') }}</p>
    <UserNameDisplayCard class="mb-4" />
    <SystemSettingsCard />
  </v-container>
</template>
