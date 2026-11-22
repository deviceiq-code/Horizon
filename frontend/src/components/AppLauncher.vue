<script setup lang="ts">
/** The suite's app launcher (the "waffle" of the top bar): every app, the current one marked. */
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute } from 'vue-router'
import { appName, SUITE_APPS, type SuiteApp } from '@/apps'
import { appModules } from '@/modules'
import { useAuthStore } from '@/stores/auth'

const route = useRoute()
const { t } = useI18n()
const auth = useAuthStore()

const current = computed(() => route.meta.app as string | undefined)

/** First page of an app the user can open (undefined when it is not available). */
function firstPage(app: SuiteApp) {
  if (app.comingSoon) return undefined
  const first = appModules(app.id, !!auth.user?.is_admin)[0]
  return first ? { name: first.name } : undefined
}
</script>

<template>
  <v-menu location="bottom start">
    <template #activator="{ props: menu }">
      <v-btn
        v-bind="menu"
        icon="mdi-dots-grid"
        variant="text"
        size="small"
        class="launcher-button"
        :aria-label="$t('apps.launcher')"
        :title="$t('apps.launcher')"
        data-testid="app-launcher"
      />
    </template>
    <v-card min-width="320" data-testid="app-launcher-menu">
      <v-card-subtitle class="pt-3">{{ $t('apps.launcher') }}</v-card-subtitle>
      <v-list density="comfortable" nav>
        <v-list-item
          :to="{ name: 'home' }"
          exact
          prepend-icon="mdi-view-grid-outline"
          :title="$t('apps.home')"
          data-testid="launcher-home"
        />
        <v-divider class="my-1" />
        <v-list-item
          v-for="app in SUITE_APPS"
          :key="app.id"
          :to="firstPage(app)"
          :disabled="!firstPage(app)"
          :active="current === app.id"
          :prepend-icon="app.icon"
          :title="appName(app, t)"
          :subtitle="app.comingSoon ? $t('apps.comingSoon') : undefined"
          color="primary"
          :data-testid="`launcher-${app.id}`"
        />
      </v-list>
    </v-card>
  </v-menu>
</template>

<style scoped>
/* Light, as the other icons of the top bar */
.launcher-button {
  color: rgba(var(--v-theme-on-background), 0.78);
}
.launcher-button :deep(.v-icon) {
  font-size: 22px;
}
</style>
