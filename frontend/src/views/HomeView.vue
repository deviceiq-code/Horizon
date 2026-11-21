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
    <!-- Welcome banner: the theme's primary color fading into the side menu's -->
    <div class="welcome mb-6" data-testid="welcome">
      <h1 class="welcome-title">{{ $t('home.welcome', { name: auth.user?.name }) }}</h1>
      <p class="welcome-text">{{ $t('home.text') }}</p>
    </div>

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
.welcome {
  padding: 32px;
  border-radius: 16px;
  color: #fff;
  background:
    radial-gradient(120% 140% at 100% 0%, rgba(255, 255, 255, 0.12) 0%, transparent 55%),
    linear-gradient(
      120deg,
      rgb(var(--v-theme-primary)) 0%,
      color-mix(in srgb, rgb(var(--v-theme-primary)) 45%, rgb(var(--v-theme-sidebar))) 55%,
      rgb(var(--v-theme-sidebar)) 100%
    );
}
/* Over the generic page title rule (main.css): larger, white */
.welcome .welcome-title {
  font-size: 1.875rem;
  font-weight: 700;
  color: #fff;
  margin: 0 0 4px;
}
.welcome-text {
  margin: 0;
  opacity: 0.85;
}
.app-card {
  transition: transform 0.15s;
}
.app-card:not(.v-card--disabled):hover {
  transform: translateY(-2px);
}
</style>
