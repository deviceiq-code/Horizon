<script setup lang="ts">
import { onBeforeUnmount, ref, watch } from 'vue'
import { RouterView } from 'vue-router'
import { useTheme } from 'vuetify'
import { useNotificationsStore } from '@/stores/notifications'
import { usePreferencesStore } from '@/stores/preferences'
import { colorThemeById, vuetifyThemeName } from '@/themes'
import { uiScaleFactor } from '@/uiScale'
import { applyFavicon } from '@/favicon'
import { installSelectOnFocus } from '@/smartTools'
import { useAuthStore } from '@/stores/auth'
import { useDictionaryStore } from '@/stores/dictionary'
import { installWordDictionary } from '@/wordDictionary'
import { installTidySpaces } from '@/tidySpaces'

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

// The browser tab's icon in the theme's brand color (German Powerhouse: CHG Red)
watch(
  () => [preferences.colorTheme, preferences.theme, systemDark.value] as const,
  ([colorTheme, mode, osDark]) => {
    const theme = colorThemeById(colorTheme)
    const version = mode === 'dark' || (mode === 'system' && osDark) ? theme.dark : theme.light
    const brand = version.colors?.brand
    if (typeof brand === 'string') applyFavicon(brand)
  },
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

// Smart Tools: entering a text field selects its content (when the user keeps it on)
const removeSelectOnFocus = installSelectOnFocus(() => preferences.selectOnFocus)
onBeforeUnmount(removeSelectOnFocus)

const auth = useAuthStore()
// Smart Tools: text typed in forms without extra spaces, when a field is left (before the
// dictionary, so it sees the tidy text — listeners run in the order installed)
const removeTidySpaces = installTidySpaces(() => !!auth.user && preferences.trimSpaces)
onBeforeUnmount(removeTidySpaces)

// Smart Tools: words typed in forms written as the shared dictionary says, when a field is left
const dictionary = useDictionaryStore()
watch(
  () => auth.user?.id,
  (id) => {
    if (id) dictionary.load()
  },
  { immediate: true },
)
const removeWordDictionary = installWordDictionary(
  () => !!auth.user && preferences.wordDictionary,
  () => dictionary.words,
)
onBeforeUnmount(removeWordDictionary)

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
