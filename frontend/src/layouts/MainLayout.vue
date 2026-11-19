<script setup lang="ts">
import { ref, watch } from 'vue'
import { RouterView, useRouter } from 'vue-router'
import { useDisplay } from 'vuetify'
import LanguageSelector from '@/components/LanguageSelector.vue'
import { MODULES } from '@/modules'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const router = useRouter()
const { mdAndUp } = useDisplay()

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

async function logout() {
  await auth.logout()
  await router.push({ name: 'login' })
}
</script>

<template>
  <v-app-bar color="primary" density="comfortable">
    <template #prepend>
      <v-app-bar-nav-icon :aria-label="$t('menu.open')" @click="toggleMenu" />
    </template>
    <v-app-bar-title>{{ $t('app.name') }}</v-app-bar-title>
    <template #append>
      <span class="mr-2 d-none d-sm-inline">
        <v-icon icon="mdi-account" size="small" /> {{ auth.user?.name }}
      </span>
      <LanguageSelector />
      <v-btn variant="text" prepend-icon="mdi-logout" @click="logout">
        {{ $t('common.logout') }}
      </v-btn>
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
      <v-list-item
        v-for="module in MODULES"
        :key="module.name"
        :to="{ name: module.name }"
        :prepend-icon="module.icon"
        :title="$t(module.titleKey)"
      />
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
    <RouterView />
  </v-main>
</template>
