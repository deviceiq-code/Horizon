<script setup lang="ts">
/** The suite's home: one card per app (Pricing, Remarketing soon, Administration). */
import { useI18n } from 'vue-i18n'
import { appName, SUITE_APPS, type SuiteApp } from '@/apps'
import { appModules } from '@/modules'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const { t } = useI18n()

function firstPage(app: SuiteApp) {
  if (app.comingSoon) return undefined
  const first = appModules(app.id, !!auth.user?.is_admin)[0]
  return first ? { name: first.name } : undefined
}
</script>

<template>
  <v-container fluid class="module-page" style="max-width: 1200px">
    <h1 class="text-h4 mb-1">{{ $t('home.welcome', { name: auth.user?.name }) }}</h1>
    <p class="text-medium-emphasis mb-6">{{ $t('home.text') }}</p>

    <v-row>
      <v-col v-for="app in SUITE_APPS" :key="app.id" cols="12" sm="6" lg="4">
        <v-card
          :to="firstPage(app)"
          :disabled="!firstPage(app)"
          class="app-card h-100"
          :data-testid="`home-app-${app.id}`"
        >
          <v-card-item>
            <template #prepend>
              <v-avatar color="primary" variant="tonal" size="56" rounded="lg">
                <v-icon :icon="app.icon" size="30" />
              </v-avatar>
            </template>
            <v-card-title>{{ appName(app, t) }}</v-card-title>
            <v-card-subtitle v-if="app.comingSoon">
              <v-chip size="x-small" label>{{ $t('apps.comingSoon') }}</v-chip>
            </v-card-subtitle>
          </v-card-item>
          <v-card-text class="text-body-2 text-medium-emphasis">
            {{ $t(app.descriptionKey) }}
          </v-card-text>
        </v-card>
      </v-col>
    </v-row>
  </v-container>
</template>

<style scoped>
.app-card {
  transition: transform 0.15s;
}
.app-card:not(.v-card--disabled):hover {
  transform: translateY(-2px);
}
</style>
