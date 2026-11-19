<script setup lang="ts">
import { RouterView } from 'vue-router'
import { CATALOG_TABS } from './tabs'
</script>

<template>
  <v-container fluid style="max-width: 1200px">
    <h1 class="text-h5 mb-1">{{ $t('catalogs.title') }}</h1>
    <p class="text-medium-emphasis mb-4">{{ $t('catalogs.subtitle') }}</p>

    <!-- Each tab is a route, so it can be linked to and survives a page reload -->
    <v-tabs color="primary" class="mb-4" show-arrows>
      <v-tab
        v-for="tab in CATALOG_TABS"
        :key="tab.name"
        :to="{ name: tab.name }"
        :prepend-icon="tab.icon"
      >
        {{ $t(tab.titleKey) }}
      </v-tab>
    </v-tabs>

    <RouterView />
  </v-container>
</template>
