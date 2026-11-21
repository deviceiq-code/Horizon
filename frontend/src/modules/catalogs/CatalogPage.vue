<script setup lang="ts">
/**
 * The page of one catalog table (Verticals, Asset Classes, Manufacturers…): its title and
 * subtitle over the table's grid. Each table is its own item in the side menu (section
 * "Catalogs" of Administration, src/modules/catalogs/index.ts).
 */
import type { Component } from 'vue'

defineProps<{ titleKey: string; subtitleKey: string; view: Component }>()
</script>

<template>
  <v-container fluid class="module-page">
    <h1 class="mb-1">{{ $t(titleKey) }}</h1>
    <p class="text-medium-emphasis mb-4">{{ $t(subtitleKey) }}</p>
    <component :is="view" />
  </v-container>
</template>
