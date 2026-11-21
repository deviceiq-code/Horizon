<script setup lang="ts">
/**
 * The path of the page in the suite, in the top bar: Horizon › Pricing › Average Prices.
 * Built from the route: the app (meta.app) and every matched route with a meta.titleKey
 * (module, then e.g. a Catalogs tab). Every step but the last is a link.
 */
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute, type RouteLocationRaw } from 'vue-router'
import { appName, suiteApp } from '@/apps'
import { appModules } from '@/modules'
import { useAuthStore } from '@/stores/auth'

interface Crumb {
  title: string
  to?: RouteLocationRaw
}

const route = useRoute()
const { t } = useI18n()
const auth = useAuthStore()

const crumbs = computed<Crumb[]>(() => {
  const items: Crumb[] = [{ title: 'Horizon', to: { name: 'home' } }]
  const app = suiteApp(route.meta.app as string | undefined)
  if (app) {
    // The app links to its first page
    const first = appModules(app.id, !!auth.user?.is_admin)[0]
    items.push({ title: appName(app, t), to: first ? { name: first.name } : undefined })
  }
  for (const record of route.matched) {
    const key = record.meta.titleKey as string | undefined
    if (key && record.name) items.push({ title: t(key), to: { name: record.name } })
  }
  // The page itself is not a link
  const last = items[items.length - 1]
  if (last && items.length > 1) last.to = undefined
  return items
})
</script>

<template>
  <nav class="breadcrumb-bar" :aria-label="$t('menu.path')" data-testid="breadcrumbs">
    <v-breadcrumbs :items="crumbs" density="compact" class="py-0 px-1">
      <template #divider>
        <v-icon icon="mdi-chevron-right" size="small" />
      </template>
      <template #item="{ item, index }">
        <v-breadcrumbs-item
          :to="(item as Crumb).to"
          :disabled="!(item as Crumb).to"
          :class="{ 'font-weight-medium': index === crumbs.length - 1 }"
          data-testid="crumb"
        >
          {{ (item as Crumb).title }}
        </v-breadcrumbs-item>
      </template>
    </v-breadcrumbs>
  </nav>
</template>

<style scoped>
/* Inside the top bar (MainLayout): no bar of its own */
.breadcrumb-bar {
  display: flex;
  align-items: center;
  min-width: 0;
  overflow: hidden;
}
.breadcrumb-bar :deep(.v-breadcrumbs) {
  margin: 0;
  flex-wrap: nowrap;
  white-space: nowrap;
}
.breadcrumb-bar :deep(.v-breadcrumbs-item) {
  color: rgba(var(--v-theme-on-background), var(--v-medium-emphasis-opacity));
}
/* The current page reads as normal text, not as a faded disabled link */
.breadcrumb-bar :deep(.v-breadcrumbs-item--disabled) {
  opacity: 1;
  color: rgb(var(--v-theme-on-background));
}
</style>
