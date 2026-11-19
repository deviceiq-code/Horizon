<script setup lang="ts">
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { LANGUAGES } from '@/i18n'
import { useNotificationsStore } from '@/stores/notifications'
import { usePreferencesStore, type PreferencesUpdate, type Theme } from '@/stores/preferences'
import { useAuthStore } from '@/stores/auth'
import SystemSettingsCard from '@/components/SystemSettingsCard.vue'

const { t } = useI18n()
const preferences = usePreferencesStore()
const auth = useAuthStore()
const notifications = useNotificationsStore()

const saving = ref(false)

const THEMES: { value: Theme; icon: string }[] = [
  { value: 'light', icon: 'mdi-white-balance-sunny' },
  { value: 'dark', icon: 'mdi-weather-night' },
  { value: 'system', icon: 'mdi-theme-light-dark' },
]

/** Every change is saved right away; the notice already shows in the newly chosen language. */
async function save(changes: PreferencesUpdate) {
  saving.value = true
  try {
    await preferences.save(changes)
    notifications.notify(t('settings.saved'))
  } catch {
    notifications.notify(t('settings.saveError'), 'error')
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <v-container style="max-width: 900px">
    <h1 class="text-h5 mb-1">{{ $t('settings.title') }}</h1>
    <p class="text-medium-emphasis mb-6">{{ $t('settings.subtitle') }}</p>

    <v-card class="mb-4">
      <v-card-item prepend-icon="mdi-translate">
        <v-card-title>{{ $t('settings.language') }}</v-card-title>
        <v-card-subtitle>{{ $t('settings.languageDescription') }}</v-card-subtitle>
      </v-card-item>
      <v-card-text>
        <v-select
          :model-value="preferences.language"
          :items="LANGUAGES"
          item-title="name"
          item-value="code"
          :label="$t('settings.language')"
          :disabled="saving"
          hide-details
          style="max-width: 360px"
          data-testid="language-select"
          @update:model-value="save({ language: $event })"
        />
      </v-card-text>
    </v-card>

    <v-card>
      <v-card-item prepend-icon="mdi-palette-outline">
        <v-card-title>{{ $t('settings.appearance') }}</v-card-title>
        <v-card-subtitle>{{ $t('settings.themeDescription') }}</v-card-subtitle>
      </v-card-item>
      <v-card-text>
        <div class="text-body-2 mb-2">{{ $t('settings.theme') }}</div>
        <v-btn-toggle
          :model-value="preferences.theme"
          mandatory
          divided
          variant="outlined"
          color="primary"
          :disabled="saving"
          data-testid="theme-toggle"
          @update:model-value="save({ theme: $event })"
        >
          <v-btn
            v-for="item in THEMES"
            :key="item.value"
            :value="item.value"
            :prepend-icon="item.icon"
          >
            {{ $t(`settings.themes.${item.value}`) }}
          </v-btn>
        </v-btn-toggle>
      </v-card-text>
    </v-card>

    <!-- System-wide settings: administrators only -->
    <SystemSettingsCard v-if="auth.user?.is_staff" class="mt-4" />
  </v-container>
</template>
