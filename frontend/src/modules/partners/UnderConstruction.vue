<script setup lang="ts">
/**
 * A page of the "Services and Partnerships" app not built yet: what it is for and
 * what is planned (texts under `partners.<page>`). The skeleton of the app: its modules exist
 * in the menu and the router while their business rules are defined.
 */
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

const props = defineProps<{ page: string; icon: string }>()
const { tm, rt } = useI18n()

const planned = computed(() =>
  (tm(`partners.${props.page}.planned`) as unknown as unknown[]).map((item) =>
    rt(item as Parameters<typeof rt>[0]),
  ),
)
</script>

<template>
  <v-container fluid class="module-page">
    <h1 class="mb-1">{{ $t(`partners.${page}.title`) }}</h1>
    <p class="text-medium-emphasis mb-4">{{ $t(`partners.${page}.subtitle`) }}</p>
    <v-card class="pa-6" data-testid="under-construction">
      <div class="d-flex align-center ga-4 mb-4">
        <v-avatar color="primary" variant="tonal" size="56" rounded="lg">
          <v-icon :icon="icon" size="32" />
        </v-avatar>
        <div>
          <v-chip size="small" color="warning" variant="tonal" label class="mb-1">
            {{ $t('partners.underConstruction') }}
          </v-chip>
          <div class="text-body-1">{{ $t('partners.underConstructionHint') }}</div>
        </div>
      </div>
      <div class="text-subtitle-2 mb-2">{{ $t('partners.planned') }}</div>
      <v-list density="compact" class="py-0" data-testid="planned">
        <v-list-item
          v-for="item in planned"
          :key="item"
          prepend-icon="mdi-checkbox-blank-circle-outline"
          :title="item"
          class="px-0"
        />
      </v-list>
    </v-card>
  </v-container>
</template>
