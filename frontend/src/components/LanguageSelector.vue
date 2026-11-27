<script setup lang="ts">
/**
 * Language switch: a globe and the current language's code ("EN"); the menu lists each
 * language by its own name with its code. Logged in, it saves to the account; on the login
 * page, only locally. `item`: a row of a menu (the user menu) — "Language" with the current
 * one, the languages opening beside it.
 */
import { computed } from 'vue'
import { LANGUAGES, type Language } from '@/i18n'
import { useAuthStore } from '@/stores/auth'
import { usePreferencesStore } from '@/stores/preferences'

defineProps<{ item?: boolean }>()

const auth = useAuthStore()
const preferences = usePreferencesStore()

/** "pt-br" → "PT" */
const code = (language: string) => language.split('-')[0]!.toUpperCase()
const current = computed(() => code(preferences.language))
const currentName = computed(
  () => LANGUAGES.find((l) => l.code === preferences.language)?.name ?? current.value,
)

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
  <v-menu :location="item ? 'start' : 'bottom end'">
    <template #activator="{ props: activator }">
      <!-- In a menu: a row; it must not close the menu it is in -->
      <v-list-item
        v-if="item"
        v-bind="activator"
        prepend-icon="mdi-web"
        :title="$t('language.label')"
        data-testid="language"
        @click.stop
      >
        <template #append>
          <span class="text-body-2 text-medium-emphasis mr-1">{{ currentName }}</span>
          <v-icon icon="mdi-chevron-right" size="18" class="text-medium-emphasis" />
        </template>
      </v-list-item>
      <v-btn
        v-else
        v-bind="activator"
        variant="text"
        prepend-icon="mdi-web"
        class="px-2 language-button"
        :ripple="false"
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
  color: rgba(var(--v-theme-on-background), 0.85);
}
.language-button :deep(.v-btn__prepend .v-icon) {
  font-size: 22px;
}
/* A light background while its menu is open, as on hover */
.language-button[aria-expanded='true'] :deep(.v-btn__overlay) {
  opacity: 0.06;
}
</style>
