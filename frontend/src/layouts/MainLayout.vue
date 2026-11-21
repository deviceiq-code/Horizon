<script setup lang="ts">
/**
 * The frame of every signed-in page:
 * - Side menu (dark, the theme's "sidebar" color): the Horizon brand, Home, the current app's
 *   pages (a section named after the app) and the other apps; Settings at the bottom.
 *   Wide windows (≥ 1440 px) open it, narrower ones (e.g. 1366 × 768 notebooks) collapse it to
 *   icons (they expand while
 *   hovered); the button on the top bar opens/collapses it and the choice is remembered in this
 *   browser, separately for wide and narrow windows. Phones: a drawer over the page.
 * - Top bar (light): that button, the path of the page, the app launcher and the user.
 */
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
const { mdAndUp, width } = useDisplay()
/** From this window width the side menu starts open (narrower: collapsed to icons) */
const WIDE_MENU = 1440
const wide = computed(() => width.value >= WIDE_MENU)
const { t } = useI18n()

// The app of the page (none on the suite's home and the user's settings)
const currentApp = computed(() => suiteApp(route.meta.app as string | undefined))
const modules = computed(() =>
  currentApp.value ? appModules(currentApp.value.id, !!auth.user?.is_admin) : [],
)
/** The other apps the user can open (switching apps from the side menu) */
const otherApps = computed(() =>
  SUITE_APPS.filter(
    (app) =>
      app.id !== currentApp.value?.id &&
      !app.comingSoon &&
      appModules(app.id, !!auth.user?.is_admin).length,
  ),
)
function firstPageOf(appId: AppId) {
  return { name: appModules(appId, !!auth.user?.is_admin)[0]!.name }
}

// --- Side menu: open or collapsed ----------------------------------------------------------------

type MenuState = 'open' | 'collapsed'
const storageKey = (wide: boolean) => `horizon.sideMenu.${wide ? 'wide' : 'narrow'}`

function readChoice(wide: boolean): MenuState | null {
  try {
    const value = localStorage.getItem(storageKey(wide))
    return value === 'open' || value === 'collapsed' ? value : null
  } catch {
    return null
  }
}

/** The user's choice for wide and for narrow windows (null: by the window's width) */
const choice = ref<Record<'wide' | 'narrow', MenuState | null>>({
  wide: readChoice(true),
  narrow: readChoice(false),
})
const sizeClass = computed(() => (wide.value ? 'wide' : 'narrow'))
const collapsed = computed(
  () => (choice.value[sizeClass.value] ?? (wide.value ? 'open' : 'collapsed')) === 'collapsed',
)

// Phones: a drawer over the page, closed until the button opens it
const drawerOpen = ref(mdAndUp.value)
watch(mdAndUp, (desktop) => (drawerOpen.value = desktop))

function toggleMenu() {
  if (!mdAndUp.value) {
    drawerOpen.value = !drawerOpen.value
    return
  }
  const next: MenuState = collapsed.value ? 'open' : 'collapsed'
  choice.value = { ...choice.value, [sizeClass.value]: next }
  try {
    localStorage.setItem(storageKey(wide.value), next)
  } catch {
    /* storage unavailable: the choice lasts until the page is reloaded */
  }
}

// --- User menu ---------------------------------------------------------------------------------

const preferences = usePreferencesStore()
const notifications = useNotificationsStore()

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
  <v-navigation-drawer
    v-model="drawerOpen"
    color="sidebar"
    class="side-menu"
    :width="256"
    :rail-width="72"
    :rail="mdAndUp && collapsed"
    :expand-on-hover="mdAndUp && collapsed"
    :temporary="!mdAndUp"
    :permanent="mdAndUp"
    data-testid="side-menu"
  >
    <!-- The brand: back to the suite's home -->
    <router-link :to="{ name: 'home' }" class="brand" data-testid="brand">
      <span class="brand-mark">H</span>
      <span class="brand-name">Horizon</span>
    </router-link>

    <v-list nav density="comfortable" class="menu-list">
      <v-list-item
        :to="{ name: 'home' }"
        exact
        prepend-icon="mdi-home-outline"
        :title="$t('menu.home')"
      />

      <!-- The current app and its pages -->
      <template v-if="currentApp">
        <div class="section" data-testid="app-title">{{ appName(currentApp, t) }}</div>
        <v-list-item
          v-for="module in modules"
          :key="module.name"
          :to="{ name: module.name }"
          :prepend-icon="module.icon"
          :title="$t(module.titleKey)"
          :data-testid="`menu-${module.name}`"
        />
      </template>

      <!-- The other apps -->
      <template v-if="otherApps.length">
        <div class="section">{{ $t('menu.apps') }}</div>
        <v-list-item
          v-for="app in otherApps"
          :key="app.id"
          :to="firstPageOf(app.id)"
          :prepend-icon="app.icon"
          :title="appName(app, t)"
          :data-testid="`menu-app-${app.id}`"
        />
      </template>
    </v-list>

    <template #append>
      <v-list nav density="comfortable" class="menu-list">
        <v-list-item
          :to="{ name: 'settings' }"
          prepend-icon="mdi-cog-outline"
          :title="$t('menu.settings')"
        />
      </v-list>
    </template>
  </v-navigation-drawer>

  <v-app-bar flat height="64" class="top-bar">
    <template #prepend>
      <v-btn
        :icon="mdAndUp && !collapsed ? 'mdi-dock-left' : 'mdi-menu'"
        variant="text"
        :aria-label="$t(mdAndUp && !collapsed ? 'menu.collapse' : 'menu.open')"
        :title="$t(mdAndUp && !collapsed ? 'menu.collapse' : 'menu.open')"
        data-testid="toggle-menu"
        @click="toggleMenu"
      />
    </template>
    <!-- Where the page is: Horizon › Pricing › Average Prices -->
    <AppBreadcrumbs class="flex-grow-1" />
    <template #append>
      <AppLauncher />
      <!-- Only the signed-in user; their menu holds the account actions (language and theme
           are in Settings) -->
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
              color="primary"
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

  <v-main>
    <RouterView />
  </v-main>
</template>

<style scoped>
/* --- Side menu ------------------------------------------------------------------------------- */
.side-menu {
  border-right: 1px solid rgba(255, 255, 255, 0.08) !important;
}
.brand {
  display: flex;
  align-items: center;
  gap: 12px;
  height: 64px;
  padding: 0 20px;
  color: rgb(var(--v-theme-on-sidebar-strong));
  text-decoration: none;
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
  white-space: nowrap;
  overflow: hidden;
}
.brand-mark {
  flex: 0 0 32px;
  height: 32px;
  border-radius: 10px;
  display: grid;
  place-items: center;
  font-weight: 700;
  font-size: 1rem;
  color: rgb(var(--v-theme-on-primary));
  background: rgb(var(--v-theme-sidebar-active));
}
.brand-name {
  font-size: 1.125rem;
  font-weight: 700;
  letter-spacing: 0.01em;
}
.menu-list {
  padding: 8px 12px;
}
.menu-list :deep(.v-list-item) {
  color: rgb(var(--v-theme-on-sidebar));
  border-radius: 12px;
  min-height: 42px;
}
.menu-list :deep(.v-list-item-title) {
  font-size: 0.875rem;
  font-weight: 400;
}
.menu-list :deep(.v-list-item--active .v-list-item-title) {
  font-weight: 600;
}
.menu-list :deep(.v-list-item .v-list-item__prepend > .v-icon) {
  opacity: 1;
}
.menu-list :deep(.v-list-item:hover) {
  color: rgb(var(--v-theme-on-sidebar-strong));
}
.menu-list :deep(.v-list-item--active) {
  color: rgb(var(--v-theme-on-sidebar-strong));
  background: rgba(var(--v-theme-sidebar-active), 0.16);
}
.menu-list :deep(.v-list-item--active .v-list-item__prepend > .v-icon) {
  color: rgb(var(--v-theme-sidebar-active));
}
.menu-list :deep(.v-list-item--active > .v-list-item__overlay) {
  opacity: 0;
}
/* Section names ("PRICING", "APPS"); collapsed to icons they give way to a thin line */
.section {
  margin: 16px 12px 6px;
  font-size: 0.75rem;
  font-weight: 600;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  white-space: nowrap;
  overflow: hidden;
  color: rgba(var(--v-theme-on-sidebar), 0.75);
}
.v-navigation-drawer--rail:not(.v-navigation-drawer--is-hovering) .section {
  height: 1px;
  margin: 12px 8px;
  color: transparent;
  background: rgba(255, 255, 255, 0.1);
}
.v-navigation-drawer--rail:not(.v-navigation-drawer--is-hovering) .brand-name {
  opacity: 0;
}

/* --- Top bar: the page's background, slightly see-through, with a line under it -------------- */
.top-bar {
  background: rgba(var(--v-theme-background), 0.85) !important;
  backdrop-filter: blur(8px);
  border-bottom: 1px solid rgba(var(--v-border-color), var(--v-border-opacity)) !important;
}
/* The user button does not light up on hover or while its menu is open; the keyboard focus
   still shows */
.user-button:hover :deep(.v-btn__overlay),
.user-button.v-btn--active :deep(.v-btn__overlay),
.user-button[aria-expanded='true'] :deep(.v-btn__overlay) {
  opacity: 0;
}
</style>
