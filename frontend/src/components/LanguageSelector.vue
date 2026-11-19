<script setup lang="ts">
import { LANGUAGES, type Language } from '@/i18n'
import { useAuthStore } from '@/stores/auth'
import { usePreferencesStore } from '@/stores/preferences'

/** Quick language switch. Logged in, it saves to the account; on the login page, only locally. */
const auth = useAuthStore()
const preferences = usePreferencesStore()

async function choose(language: Language) {
  if (auth.isAuthenticated) {
    await preferences.save({ language }).catch(() => {
      /* the store already rolled back; the settings page shows the detailed error */
    })
  } else {
    preferences.apply({ language })
  }
}
</script>

<template>
  <v-menu location="bottom end">
    <template #activator="{ props: activator }">
      <v-btn
        v-bind="activator"
        icon="mdi-translate"
        variant="text"
        :aria-label="$t('language.select')"
        :title="$t('language.select')"
      />
    </template>
    <v-list density="compact" :selected="[preferences.language]">
      <v-list-item
        v-for="item in LANGUAGES"
        :key="item.code"
        :value="item.code"
        :title="item.name"
        :lang="item.code"
        @click="choose(item.code)"
      />
    </v-list>
  </v-menu>
</template>
