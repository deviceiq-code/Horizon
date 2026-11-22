<script setup lang="ts">
/**
 * Language switch: a globe and the current language's code ("EN"); the menu lists each
 * language by its own name with its code. Logged in, it saves to the account; on the login
 * page, only locally.
 */
import { computed } from 'vue'
import { LANGUAGES, type Language } from '@/i18n'
import { useAuthStore } from '@/stores/auth'
import { usePreferencesStore } from '@/stores/preferences'

const auth = useAuthStore()
const preferences = usePreferencesStore()

/** "pt-br" → "PT" */
const code = (language: string) => language.split('-')[0]!.toUpperCase()
const current = computed(() => code(preferences.language))

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
        variant="text"
        prepend-icon="mdi-web"
        class="px-2 language-button"
        :aria-label="$t('language.select')"
        :title="$t('language.select')"
        data-testid="language"
      >
        {{ current }}
      </v-btn>
    </template>
    <v-list density="comfortable" min-width="220" class="py-1" data-testid="language-menu">
      <v-list-item
        v-for="item in LANGUAGES"
        :key="item.code"
        :active="item.code === preferences.language"
        color="primary"
        :lang="item.code"
        :data-testid="`language-${item.code}`"
        @click="choose(item.code)"
      >
        <v-list-item-title>{{ item.name }}</v-list-item-title>
        <template #append>
          <span class="text-caption text-medium-emphasis ml-4">{{ code(item.code) }}</span>
        </template>
      </v-list-item>
    </v-list>
  </v-menu>
</template>

<style scoped>
.language-button {
  font-weight: 600;
  min-width: 0;
}
</style>
