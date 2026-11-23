<script setup lang="ts">
/**
 * The frame of every signed-in page:
 * - Side menu (dark, the theme's "sidebar" color): the Horizon brand, Home, the current app's
 *   pages by section (a module's `section`, e.g. Management and Catalogs in Administration;
 *   without one, a section named after the app) and the other apps; Settings at the bottom.
 *   Wide windows (≥ 1440 px) open it, narrower ones (e.g. 1366 × 768 notebooks) collapse it to
 *   icons (they expand while
 *   hovered); the button on the top bar opens/collapses it and the choice is remembered in this
 *   browser, separately for wide and narrow windows. Phones: a drawer over the page.
 * - Top bar (light): that button, the path of the page; then search, documentation and
 *   notifications (to come), light/dark mode, language, the app launcher and the user's menu
 *   (who they are and their roles; Profile and Help to come; Settings; Sign out).
 */
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { RouterView, useRoute, useRouter } from 'vue-router'
import { useDisplay, useTheme } from 'vuetify'
import { appName, SUITE_APPS, suiteApp, type AppId } from '@/apps'
import AppBreadcrumbs from '@/components/AppBreadcrumbs.vue'
import AppLauncher from '@/components/AppLauncher.vue'
import LanguageSelector from '@/components/LanguageSelector.vue'
import PersonAvatar from '@/components/PersonAvatar.vue'
import { appModules } from '@/modules'
import { userPhotoUrl } from '@/modules/users/api'
import { roleName } from '@/modules/users/roleText'
import { useAuthStore } from '@/stores/auth'
import { useNotificationsStore } from '@/stores/notifications'
import { usePreferencesStore, type Theme } from '@/stores/preferences'

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
/** The app's pages by section ("Management", "Catalogs"…; without one: the app's name) */
const sections = computed(() => {
  const groups: { title: string; key: string; modules: typeof modules.value }[] = []
  for (const module of modules.value) {
    const key = module.section ?? 'app'
    let group = groups.find((g) => g.key === key)
    if (!group) {
      const title = module.section ? t(module.section) : appName(currentApp.value!, t)
      group = { title, key, modules: [] }
      groups.push(group)
    }
    group.modules.push(module)
  }
  return groups
})
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

const preferences = usePreferencesStore()
type MenuState = 'open' | 'collapsed'

/** The user's choice for wide and for narrow windows (none: by the window's width), kept with
 * the account (preferences' ui_state) so it follows them to any computer */
const choice = computed(() => preferences.uiState.sideMenu ?? {})
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
  const size = sizeClass.value
  preferences.saveUiState((state) => ({ ...state, sideMenu: { ...state.sideMenu, [size]: next } }))
}

// --- Top bar -----------------------------------------------------------------------------------

const notifications = useNotificationsStore()
const vuetifyTheme = useTheme()
/** The interface is dark now (the user's mode, or the system's when following it) */
const isDark = computed(() => vuetifyTheme.current.value.dark)

/** Buttons whose features are not there yet */
function comingSoon(key: string) {
  notifications.notify(t('menu.comingSoon', { feature: t(key) }))
}

/** The user's roles as shown (system roles translated) */
const roleNames = computed(() =>
  (auth.user?.role_refs ?? []).map((role) => roleName({ id: 0, ...role }, t)),
)

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
    :width="288"
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

      <!-- The current app's pages, by section -->
      <template v-for="(group, index) in sections" :key="group.key">
        <div class="section" :data-testid="index === 0 ? 'app-title' : `section-${group.key}`">
          {{ group.title }}
        </div>
        <v-list-item
          v-for="module in group.modules"
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
      <div class="d-flex align-center ga-1 mr-1">
        <!-- Search, documentation and notifications: to come -->
        <v-btn
          icon="mdi-magnify"
          variant="text"
          size="small"
          class="bar-icon"
          :title="$t('menu.search')"
          :aria-label="$t('menu.search')"
          data-testid="search"
          @click="comingSoon('menu.search')"
        />
        <v-btn
          icon="mdi-book-open-outline"
          variant="text"
          size="small"
          class="bar-icon"
          :title="$t('menu.docs')"
          :aria-label="$t('menu.docs')"
          data-testid="docs"
          @click="comingSoon('menu.docs')"
        />
        <!-- Light / dark, right away (saved to the account) -->
        <v-btn
          :icon="isDark ? 'mdi-white-balance-sunny' : 'mdi-moon-waning-crescent'"
          variant="text"
          size="small"
          class="bar-icon"
          :title="$t(isDark ? 'menu.lightMode' : 'menu.darkMode')"
          :aria-label="$t(isDark ? 'menu.lightMode' : 'menu.darkMode')"
          data-testid="theme-switch"
          @click="setTheme(isDark ? 'light' : 'dark')"
        />
        <LanguageSelector />
        <v-btn
          icon="mdi-bell-outline"
          variant="text"
          size="small"
          class="bar-icon"
          :title="$t('menu.notifications')"
          :aria-label="$t('menu.notifications')"
          data-testid="notifications"
          @click="comingSoon('menu.notifications')"
        />
        <AppLauncher />
      </div>
      <!-- The signed-in user: who they are, their pages and signing out -->
      <v-menu v-if="auth.user" location="bottom end">
        <template #activator="{ props: menu }">
          <v-btn
            v-bind="menu"
            variant="text"
            class="user-button text-none pl-1 pr-2 mr-2"
            rounded="pill"
            :ripple="false"
            :aria-label="$t('menu.account')"
            data-testid="me"
          >
            <PersonAvatar
              :name="auth.user.name"
              :src="
                auth.user.photo_version ? userPhotoUrl(auth.user.id, auth.user.photo_version) : null
              "
              :size="34"
              color="primary"
              class="user-avatar"
            />
            <span class="ml-2 d-none d-sm-inline user-name">{{ auth.user.name }}</span>
            <v-icon icon="mdi-chevron-down" size="18" class="ml-1 bar-muted" />
          </v-btn>
        </template>
        <v-card min-width="260" class="user-menu" data-testid="user-menu">
          <div class="pa-4 pb-3">
            <div class="font-weight-bold">{{ auth.user.name }}</div>
            <div v-if="auth.user.email" class="text-body-2 text-medium-emphasis">
              {{ auth.user.email }}
            </div>
            <div v-if="roleNames.length" class="d-flex flex-wrap ga-1 mt-2">
              <v-chip v-for="role in roleNames" :key="role" size="small" data-testid="user-role">
                {{ role }}
              </v-chip>
            </div>
          </div>
          <v-divider />
          <v-list density="compact" class="py-1">
            <v-list-item
              :title="$t('menu.profile')"
              data-testid="user-profile"
              @click="comingSoon('menu.profile')"
            />
            <v-list-item
              :to="{ name: 'settings' }"
              :title="$t('menu.settings')"
              data-testid="user-settings"
            />
            <v-list-item
              :title="$t('menu.help')"
              data-testid="user-help"
              @click="comingSoon('menu.help')"
            />
          </v-list>
          <v-divider />
          <v-list density="compact" class="py-1">
            <v-list-item
              prepend-icon="mdi-logout"
              :title="$t('common.logout')"
              base-color="error"
              data-testid="logout"
              @click="logout"
            />
          </v-list>
        </v-card>
      </v-menu>
    </template>
  </v-app-bar>

  <v-main>
    <RouterView />
  </v-main>
</template>

<style scoped>
/* --- Top bar: light icons, no backgrounds until hovered -------------------------------------- */
.bar-icon {
  color: rgba(var(--v-theme-on-background), 0.78);
}
.bar-icon :deep(.v-icon) {
  font-size: 22px;
}
.bar-muted {
  opacity: 0.6;
}
.user-name {
  font-weight: 500;
}
/* User menu: the sign-out icon close to its text */
.user-menu :deep(.v-list-item__spacer) {
  width: 12px !important;
}
.user-avatar {
  box-shadow:
    0 0 0 2px rgba(var(--v-theme-surface), 1),
    0 0 0 3px rgba(var(--v-border-color), 0.2);
}

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
