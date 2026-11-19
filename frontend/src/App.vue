<script setup lang="ts">
import { watch } from 'vue'
import { RouterView } from 'vue-router'
import { useTheme } from 'vuetify'
import { useNotificationsStore } from '@/stores/notifications'
import { usePreferencesStore } from '@/stores/preferences'

const preferences = usePreferencesStore()
const notifications = useNotificationsStore()
const vuetifyTheme = useTheme()

// Preference values match Vuetify's theme names ('system' follows the operating system)
watch(
  () => preferences.theme,
  (theme) => vuetifyTheme.change(theme),
  { immediate: true },
)
</script>

<template>
  <v-app>
    <RouterView />

    <v-snackbar
      v-model="notifications.visible"
      :color="notifications.color"
      :timeout="notifications.color === 'error' ? 5000 : 2500"
    >
      {{ notifications.text }}
    </v-snackbar>
  </v-app>
</template>
