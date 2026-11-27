<script setup lang="ts">
/**
 * Search: one search over every module (src/search.ts). The query and the category are in the
 * address (?q=&category=), so a search can be shared or reopened. All: a few results of each
 * category with its count; a category's tab: more of it. Pages are found by their names.
 */
import { computed, onMounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute, useRouter } from 'vue-router'
import HighlightText from '@/components/HighlightText.vue'
import PersonAvatar from '@/components/PersonAvatar.vue'
import { userPhotoUrl } from '@/modules/users/api'
import {
  categoryInfo,
  MIN_QUERY,
  resultTarget,
  searchAll,
  searchPages,
  type SearchCategory,
  type SearchResult,
} from '@/search'
import { useAuthStore } from '@/stores/auth'
import { formatMoney } from '@/utils/money'

const { t, locale } = useI18n()
const route = useRoute()
const router = useRouter()
const auth = useAuthStore()

const input = ref(typeof route.query.q === 'string' ? route.query.q : '')
const q = ref(input.value.trim())
const category = ref(typeof route.query.category === 'string' ? route.query.category : 'all')

const categories = ref<SearchCategory[]>([])
const loading = ref(false)
const failed = ref(false)
let lastRequest = 0

const field = ref<{ focus: () => void } | null>(null)
onMounted(() => field.value?.focus())

// Typing: searched after a pause; the address follows (replace: no history per letter)
let timer: ReturnType<typeof setTimeout> | undefined
watch(input, (value) => {
  clearTimeout(timer)
  timer = setTimeout(() => {
    q.value = value.trim()
    category.value = 'all'
  }, 300)
})
watch([q, category], () => {
  router.replace({
    query: {
      ...(q.value ? { q: q.value } : {}),
      ...(category.value !== 'all' ? { category: category.value } : {}),
    },
  })
  load()
})
onMounted(load)

async function load() {
  const request = ++lastRequest
  failed.value = false
  if (q.value.length < MIN_QUERY) {
    categories.value = []
    return
  }
  loading.value = true
  try {
    const data = await searchAll(q.value, category.value === 'all' ? '' : category.value)
    if (request === lastRequest) categories.value = data.categories
  } catch {
    if (request === lastRequest) failed.value = true
  } finally {
    if (request === lastRequest) loading.value = false
  }
}

const pages = computed(() =>
  q.value.length < MIN_QUERY ? [] : searchPages(q.value, !!auth.user?.is_admin, t),
)

/** Tabs: All and each category with results (pages first), with their counts */
const tabs = computed(() => [
  ...(pages.value.length ? [{ key: 'pages', count: pages.value.length }] : []),
  ...categories.value.map((c) => ({ key: c.key, count: c.count })),
])
const total = computed(() => tabs.value.reduce((sum, tab) => sum + tab.count, 0))

/** The groups shown: every one (All) or the chosen category */
const shown = computed(() => tabs.value.filter((tab) => ['all', tab.key].includes(category.value)))
const resultsOf = (key: string) => categories.value.find((c) => c.key === key)?.results ?? []
/** On All, a few of each: "View All (N)" opens its tab */
const PAGES_ON_ALL = 5
const pagesShown = computed(() =>
  category.value === 'all' ? pages.value.slice(0, PAGES_ON_ALL) : pages.value,
)
const shownCount = (key: string) =>
  key === 'pages' ? pagesShown.value.length : resultsOf(key).length

const money = (result: SearchResult) =>
  result.amount ? formatMoney(result.amount.value, result.amount.currency, locale.value) : ''

function open(key: string, result: SearchResult) {
  router.push(resultTarget(key, result))
}
</script>

<template>
  <v-container fluid class="module-page search-page">
    <h1 class="mb-1">{{ $t(q ? 'search.resultsTitle' : 'search.title') }}</h1>
    <p class="text-medium-emphasis mb-4">{{ $t('search.subtitle') }}</p>

    <!-- The search field: large, focused on arrival -->
    <v-text-field
      ref="field"
      v-model="input"
      :placeholder="$t('search.placeholder')"
      prepend-inner-icon="mdi-magnify"
      variant="outlined"
      density="default"
      clearable
      hide-details
      autocomplete="off"
      class="search-field mb-4"
      data-testid="search-input"
      @keydown.enter="q = input.trim()"
    >
      <template #append-inner>
        <span class="shortcut text-caption text-medium-emphasis">{{ $t('search.shortcut') }}</span>
      </template>
    </v-text-field>

    <v-progress-linear v-if="loading" indeterminate color="primary" class="mb-2" />

    <!-- Before typing: what can be found -->
    <div v-if="q.length < MIN_QUERY" class="state" data-testid="search-start">
      <v-icon icon="mdi-magnify" size="48" class="state-icon mb-4" />
      <div class="text-h6 font-weight-medium">{{ $t('search.startTitle') }}</div>
      <div class="text-body-1 text-medium-emphasis mt-1">{{ $t('search.startHint') }}</div>
    </div>

    <v-alert v-else-if="failed" type="error" variant="tonal">
      {{ $t('common.loadError') }}
      <template #append>
        <v-btn variant="text" size="small" @click="load">{{ $t('common.retry') }}</v-btn>
      </template>
    </v-alert>

    <template v-else-if="!loading || tabs.length">
      <!-- Nothing found -->
      <div v-if="!tabs.length && !loading" class="state" data-testid="search-none">
        <v-icon icon="mdi-text-search-variant" size="48" class="state-icon mb-4" />
        <div class="text-h6 font-weight-medium">{{ $t('search.noneTitle') }}</div>
        <div class="text-body-1 text-medium-emphasis mt-1">{{ $t('search.noneHint') }}</div>
      </div>

      <template v-else>
        <div class="text-body-2 text-medium-emphasis mb-2" data-testid="search-count">
          {{ $t('search.found', { n: total, q }, total) }}
        </div>

        <v-tabs
          v-model="category"
          color="primary"
          show-arrows
          class="mb-4"
          data-testid="search-tabs"
        >
          <v-tab value="all" data-testid="search-tab-all">
            {{ $t('search.all') }} ({{ total }})
          </v-tab>
          <v-tab
            v-for="tab in tabs"
            :key="tab.key"
            :value="tab.key"
            :data-testid="`search-tab-${tab.key}`"
          >
            {{ $t(categoryInfo(tab.key).titleKey) }} ({{ tab.count }})
          </v-tab>
        </v-tabs>

        <!-- Grouped by category: heading, then its results -->
        <v-card
          v-for="group in shown"
          :key="group.key"
          class="mb-4"
          :data-testid="`search-group-${group.key}`"
        >
          <div class="group-title d-flex align-center">
            <v-icon :icon="categoryInfo(group.key).icon" size="18" class="mr-2" />
            <span class="flex-grow-1">{{ $t(categoryInfo(group.key).titleKey) }}</span>
            <v-btn
              v-if="category === 'all' && group.count > shownCount(group.key)"
              variant="text"
              size="small"
              color="primary"
              class="text-none"
              :data-testid="`search-more-${group.key}`"
              @click="category = group.key"
            >
              {{ $t('search.viewAll', { n: group.count }) }}
            </v-btn>
          </div>

          <!-- Pages: the module's icon, its name and where it is -->
          <template v-if="group.key === 'pages'">
            <template v-for="(page, index) in pagesShown" :key="page.name">
              <v-divider v-if="index" class="mx-5" />
              <router-link :to="{ name: page.name }" class="result" data-testid="search-result">
                <v-avatar color="primary" variant="tonal" size="40">
                  <v-icon :icon="page.icon" size="20" />
                </v-avatar>
                <div class="flex-grow-1 min-w-0">
                  <div class="result-title"><HighlightText :text="page.title" :q="q" /></div>
                  <div v-if="page.subtitle" class="text-body-2 text-medium-emphasis">
                    {{ page.subtitle }}
                  </div>
                </div>
              </router-link>
            </template>
          </template>

          <!-- Records: the same look in every category -->
          <template v-else>
            <template v-for="(result, index) in resultsOf(group.key)" :key="result.id">
              <v-divider v-if="index" class="mx-5" />
              <a
                :href="router.resolve(resultTarget(group.key, result)).href"
                class="result"
                data-testid="search-result"
                @click.prevent="open(group.key, result)"
              >
                <PersonAvatar
                  v-if="group.key === 'users'"
                  :name="result.title"
                  :src="result.photo_version ? userPhotoUrl(result.id, result.photo_version) : null"
                  :size="40"
                />
                <v-avatar v-else color="primary" variant="tonal" size="40">
                  <v-icon :icon="result.icon || categoryInfo(group.key).icon" size="20" />
                </v-avatar>
                <div class="flex-grow-1 min-w-0">
                  <div class="result-title"><HighlightText :text="result.title" :q="q" /></div>
                  <div v-if="result.subtitle" class="text-body-2 text-medium-emphasis">
                    <HighlightText :text="result.subtitle" :q="q" />
                  </div>
                  <div v-if="result.meta" class="text-caption text-disabled text-truncate">
                    <HighlightText :text="result.meta" :q="q" />
                  </div>
                </div>
                <div class="d-flex flex-column align-end ga-1 flex-shrink-0">
                  <span v-if="result.amount" class="font-weight-medium numeric">
                    {{ money(result) }}
                  </span>
                  <v-chip
                    v-if="result.badge"
                    :color="result.badge.color"
                    size="small"
                    variant="tonal"
                    data-testid="search-badge"
                  >
                    {{ result.badge.text }}
                  </v-chip>
                </div>
              </a>
            </template>
          </template>
        </v-card>
      </template>
    </template>
  </v-container>
</template>

<style scoped>
.search-field :deep(.v-field) {
  font-size: 1.05rem;
}
.shortcut {
  border: 1px solid rgba(var(--v-border-color), var(--v-border-opacity));
  border-radius: 6px;
  padding: 1px 6px;
  white-space: nowrap;
}
.state {
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
  padding: 56px 24px;
}
.state-icon {
  color: rgba(var(--v-theme-on-surface), var(--v-medium-emphasis-opacity));
}
.group-title {
  padding: 14px 20px 6px;
  font-size: 0.75rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: rgba(var(--v-theme-on-surface), var(--v-medium-emphasis-opacity));
}
.result {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 12px 20px;
  color: inherit;
  text-decoration: none;
  transition: background-color 0.15s;
}
.result:hover {
  background: rgba(var(--v-theme-on-surface), 0.04);
}
.result:focus-visible {
  outline: 2px solid rgb(var(--v-theme-primary));
  outline-offset: -2px;
}
.result-title {
  font-weight: 600;
}
.min-w-0 {
  min-width: 0;
}
.numeric {
  font-variant-numeric: tabular-nums;
}
</style>
