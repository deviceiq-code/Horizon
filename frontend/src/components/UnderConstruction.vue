<script setup lang="ts">
/**
 * A page of an app not built yet (an app's skeleton — Services and Partnerships, Remarketing):
 * what it is for and what is planned, texts under `textKey` (`title`, `subtitle`, `planned`
 * — a list). Its modules exist in the menu and the router while their business rules are
 * defined.
 */
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

const props = defineProps<{ textKey: string; icon: string }>()
const { tm, rt } = useI18n()

const planned = computed(() =>
  (tm(`${props.textKey}.planned`) as unknown as unknown[]).map((item) =>
    rt(item as Parameters<typeof rt>[0]),
  ),
)
</script>

<template>
  <v-container fluid class="module-page">
    <h1 class="mb-1">{{ $t(`${textKey}.title`) }}</h1>
    <p class="text-medium-emphasis mb-4">{{ $t(`${textKey}.subtitle`) }}</p>
    <v-card class="pa-6" data-testid="under-construction">
      <div class="d-flex align-center ga-4 mb-4">
        <v-avatar color="primary" variant="tonal" size="56" rounded="lg">
          <v-icon :icon="icon" size="32" />
        </v-avatar>
        <div>
          <v-chip size="small" color="warning" variant="tonal" label class="mb-1">
            {{ $t('underConstruction.label') }}
          </v-chip>
          <div class="text-body-1">{{ $t('underConstruction.hint') }}</div>
        </div>
      </div>
      <div class="text-subtitle-2 mb-2">{{ $t('underConstruction.planned') }}</div>
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
