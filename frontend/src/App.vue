<script setup lang="ts">
import { onBeforeUnmount, ref, watch } from 'vue'
import { RouterView } from 'vue-router'
import { useTheme } from 'vuetify'
import { useNotificationsStore } from '@/stores/notifications'
import { usePreferencesStore } from '@/stores/preferences'
import { colorThemeById, vuetifyThemeName } from '@/themes'
import { uiScaleFactor } from '@/uiScale'

const preferences = usePreferencesStore()
const notifications = useNotificationsStore()
const vuetifyTheme = useTheme()

// "System" follows the operating system's light/dark setting, also when it changes
const systemDark = ref(false)
const media = window.matchMedia?.('(prefers-color-scheme: dark)')
const onSystemChange = () => (systemDark.value = !!media?.matches)
onSystemChange()
media?.addEventListener?.('change', onSystemChange)
onBeforeUnmount(() => media?.removeEventListener?.('change', onSystemChange))

// The color theme in its light or dark version
watch(
  () => [preferences.colorTheme, preferences.theme, systemDark.value] as const,
  ([colorTheme, mode, osDark]) =>
    vuetifyTheme.change(
      vuetifyThemeName(colorTheme, mode === 'dark' || (mode === 'system' && osDark)),
    ),
  { immediate: true },
)

// The theme's font
watch(
  () => preferences.colorTheme,
  (id) =>
    document.documentElement.style.setProperty(
      '--horizon-font-family',
      colorThemeById(id).fontFamily,
    ),
  { immediate: true },
)

// Size of the interface: zoom of the whole page (text, spacing, fields), from the user's
// choice or — "auto" — the window's width (src/uiScale.ts). `--ui-zoom` lets layouts that
// use the window's height (vh) undo it (main.css).
const windowWidth = ref(window.innerWidth)
const onResize = () => (windowWidth.value = window.innerWidth)
window.addEventListener('resize', onResize)
onBeforeUnmount(() => window.removeEventListener('resize', onResize))
watch(
  () => uiScaleFactor(preferences.uiScale, windowWidth.value),
  (scale) => {
    const root = document.documentElement
    root.style.zoom = scale === 1 ? '' : String(scale)
    root.style.setProperty('--ui-zoom', String(scale))
  },
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
