<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { RouterView, useRoute, useRouter } from 'vue-router'
import { useDisplay } from 'vuetify'
import { appName, SUITE_APPS, suiteApp, type AppId } from '@/apps'
import AppBreadcrumbs from '@/components/AppBreadcrumbs.vue'
import AppLauncher from '@/components/AppLauncher.vue'
import PersonAvatar from '@/components/PersonAvatar.vue'
import { appModules } from '@/modules'
import { userPhotoUrl } from '@/modules/users/api'
import { useAuthStore } from '@/stores/auth'
import { useNotificationsStore } from '@/stores/notifications'
import { THEME_OPTIONS, usePreferencesStore, type Theme } from '@/stores/preferences'

const auth = useAuthStore()
const route = useRoute()
const router = useRouter()
const { mdAndUp } = useDisplay()

// The app of the page (none on the suite's home and the user's settings)
const currentApp = computed(() => suiteApp(route.meta.app as string | undefined))
// Side menu: the current app's modules; outside an app, the apps themselves
const modules = computed(() =>
  currentApp.value ? appModules(currentApp.value.id, !!auth.user?.is_admin) : [],
)
const openApps = computed(() =>
  SUITE_APPS.filter((app) => !app.comingSoon && appModules(app.id, !!auth.user?.is_admin).length),
)
function firstPageOf(appId: AppId) {
  return { name: appModules(appId, !!auth.user?.is_admin)[0]!.name }
}

// Desktop: permanent icon rail that expands on hover; the top-left button pins it open.
// Mobile: hidden drawer that the top-left button opens over the page.
const drawerOpen = ref(mdAndUp.value)
const rail = ref(true)

watch(mdAndUp, (desktop) => {
  drawerOpen.value = desktop
})

function toggleMenu() {
  if (mdAndUp.value) rail.value = !rail.value
  else drawerOpen.value = !drawerOpen.value
}

const preferences = usePreferencesStore()
const notifications = useNotificationsStore()
const { t } = useI18n()
const title = computed(() => (currentApp.value ? appName(currentApp.value, t) : 'Horizon'))

async function setTheme(theme: Theme) {
  if (theme === preferences.theme) return
  try {
    await preferences.save({ theme })
  } catch {
    notifications.notify(t('settings.saveError'), 'error')
  }
}

async function logout() {
  await auth.logout()
  await router.push({ name: 'login' })
}
</script>

<template>
  <v-app-bar color="app-bar" density="comfortable" class="app-bar">
    <template #prepend>
      <v-app-bar-nav-icon :aria-label="$t('menu.open')" @click="toggleMenu" />
      <AppLauncher />
    </template>
    <!-- "Pricing", "Administração"… or just "Horizon" outside an app -->
    <v-app-bar-title data-testid="app-title">{{ title }}</v-app-bar-title>
    <!-- Only the signed-in user; their menu holds the account actions (language and theme
         are in Settings) -->
    <template #append>
      <v-menu v-if="auth.user" location="bottom end" :close-on-content-click="false">
        <template #activator="{ props: menu }">
          <v-btn
            v-bind="menu"
            variant="text"
            class="user-button text-none px-2 mr-1"
            :ripple="false"
            :aria-label="$t('menu.account')"
            data-testid="me"
          >
            <PersonAvatar
              :name="auth.user.name"
              :src="
                auth.user.photo_version ? userPhotoUrl(auth.user.id, auth.user.photo_version) : null
              "
              :size="32"
              color="surface"
            />
            <span class="ml-2 d-none d-sm-inline">{{ auth.user.name }}</span>
            <v-icon icon="mdi-chevron-down" size="small" class="ml-1" />
          </v-btn>
        </template>
        <v-list density="compact" min-width="320" data-testid="user-menu">
          <!-- Appearance: applied right away and saved to the account -->
          <v-list-subheader>{{ $t('settings.appearance') }}</v-list-subheader>
          <div class="px-3 pb-2">
            <v-btn-toggle
              :model-value="preferences.theme"
              mandatory
              divided
              density="compact"
              variant="outlined"
              color="primary"
              class="w-100"
              data-testid="theme-toggle"
              @update:model-value="setTheme"
            >
              <v-btn
                v-for="option in THEME_OPTIONS"
                :key="option.value"
                :value="option.value"
                :prepend-icon="option.icon"
                class="flex-grow-1 text-none"
                size="small"
                :data-testid="`theme-${option.value}`"
              >
                {{ $t(`settings.themes.${option.value}`) }}
              </v-btn>
            </v-btn-toggle>
          </div>
          <v-divider class="my-1" />
          <v-list-item
            :to="{ name: 'settings' }"
            prepend-icon="mdi-cog-outline"
            :title="$t('menu.settings')"
            data-testid="user-settings"
          />
          <v-list-item
            prepend-icon="mdi-logout"
            :title="$t('common.logout')"
            data-testid="logout"
            @click="logout"
          />
        </v-list>
      </v-menu>
    </template>
  </v-app-bar>

  <v-navigation-drawer
    v-model="drawerOpen"
    :rail="mdAndUp && rail"
    :expand-on-hover="mdAndUp && rail"
    :temporary="!mdAndUp"
    :permanent="mdAndUp"
  >
    <v-list nav density="comfortable">
      <v-list-item
        :to="{ name: 'home' }"
        exact
        prepend-icon="mdi-home-outline"
        :title="$t('menu.home')"
      />
      <v-divider class="my-1" />
      <!-- Inside an app: its pages -->
      <v-list-item
        v-for="module in modules"
        :key="module.name"
        :to="{ name: module.name }"
        :prepend-icon="module.icon"
        :title="$t(module.titleKey)"
        :data-testid="`menu-${module.name}`"
      />
      <!-- Outside an app: the apps -->
      <template v-if="!currentApp">
        <v-list-item
          v-for="app in openApps"
          :key="app.id"
          :to="firstPageOf(app.id)"
          :prepend-icon="app.icon"
          :title="appName(app, t)"
          :data-testid="`menu-app-${app.id}`"
        />
      </template>
    </v-list>

    <template #append>
      <v-list nav density="comfortable">
        <v-list-item
          :to="{ name: 'settings' }"
          prepend-icon="mdi-cog-outline"
          :title="$t('menu.settings')"
        />
      </v-list>
    </template>
  </v-navigation-drawer>

  <v-main>
    <AppBreadcrumbs />
    <RouterView />
  </v-main>
</template>

<style scoped>
/* The user button does not light up on hover or while its menu is open; the keyboard focus
   still shows */
.user-button:hover :deep(.v-btn__overlay),
.user-button.v-btn--active :deep(.v-btn__overlay),
.user-button[aria-expanded='true'] :deep(.v-btn__overlay) {
  opacity: 0;
}
/* A metallic sheen with the theme's top bar colors (app-bar → app-bar-end) */
.app-bar {
  background: linear-gradient(
    100deg,
    rgb(var(--v-theme-app-bar)) 0%,
    rgb(var(--v-theme-app-bar)) 45%,
    rgb(var(--v-theme-app-bar-end)) 100%
  ) !important;
}
</style>
