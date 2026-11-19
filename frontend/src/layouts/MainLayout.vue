<script setup lang="ts">
import { ref } from 'vue'
import { RouterView, useRouter } from 'vue-router'
import { useDisplay } from 'vuetify'
import LanguageSelector from '@/components/LanguageSelector.vue'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const router = useRouter()
const { mdAndUp } = useDisplay()

const menuOpen = ref(mdAndUp.value)

async function logout() {
  await auth.logout()
  await router.push({ name: 'login' })
}
</script>

<template>
  <v-app-bar color="primary" density="comfortable">
    <template #prepend>
      <v-app-bar-nav-icon :aria-label="$t('menu.open')" @click="menuOpen = !menuOpen" />
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

  <v-navigation-drawer v-model="menuOpen" :temporary="!mdAndUp">
    <v-list nav density="comfortable">
      <v-list-item
        :to="{ name: 'home' }"
        exact
        prepend-icon="mdi-home-outline"
        :title="$t('menu.home')"
      />
      <v-list-item
        :to="{ name: 'settings' }"
        prepend-icon="mdi-cog-outline"
        :title="$t('menu.settings')"
      />
    </v-list>
  </v-navigation-drawer>

  <v-main>
    <RouterView />
  </v-main>
</template>
