<script setup lang="ts">
/**
 * Settings › App Settings (administrators only): the settings of each app of the suite, one
 * section per app (src/apps.ts order). They are the system's, not the user's: they apply to
 * everyone. An app's settings are its component in APP_SETTINGS; an app without one shows
 * that it has none yet.
 */
import type { Component } from 'vue'
import { useI18n } from 'vue-i18n'
import { appName, SUITE_APPS, type AppId } from '@/apps'
import SettingRow from '@/components/SettingRow.vue'
import PricingSettingsSection from '@/modules/pricing-settings/PricingSettingsSection.vue'

const APP_SETTINGS: Partial<Record<AppId, Component>> = {
  pricing: PricingSettingsSection,
}

const { t } = useI18n()
</script>

<template>
  <p class="text-medium-emphasis mb-6" data-testid="app-settings-hint">
    {{ $t('settings.appSettings.hint') }}
  </p>
  <section
    v-for="app in SUITE_APPS"
    :key="app.id"
    class="app-section"
    :data-testid="`app-settings-${app.id}`"
  >
    <h2 class="app-section__title">
      <v-icon :icon="app.icon" size="small" color="primary" />
      {{ appName(app, t) }}
    </h2>
    <component :is="APP_SETTINGS[app.id]" v-if="APP_SETTINGS[app.id]" />
    <v-card v-else class="mb-6">
      <SettingRow
        :title="$t('settings.appSettings.noneTitle')"
        :description="$t('settings.appSettings.none')"
      />
    </v-card>
  </section>
</template>

<style scoped>
.app-section + .app-section {
  margin-top: 8px;
}
.app-section__title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 1.125rem;
  font-weight: 600;
  margin: 0 0 12px;
}
</style>
