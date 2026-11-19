<script setup lang="ts">
import { watch } from 'vue'
import { RouterView } from 'vue-router'
import { useTheme } from 'vuetify'
import { usePreferencesStore } from '@/stores/preferences'

const preferences = usePreferencesStore()
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
  </v-app>
</template>
