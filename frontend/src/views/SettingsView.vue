<script setup lang="ts">
/**
 * The user's own settings, in tabs — Language and Region (language, date and time, numbers and
 * currency), Appearance (mode, color theme, interface size) and Smart Tools —, saved to their
 * account (the database), so they follow the user to any computer. Laid out as Haze's settings:
 * full width, cards of rows, each with its title and description on the left and the control
 * on the right (SettingRow). Global settings are in Administration → System Settings.
 */
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { normalizeDecimal } from '@/utils/decimal'
import { formatMoney, toInputNumber } from '@/utils/money'
import { useI18n } from 'vue-i18n'
import { LANGUAGES } from '@/i18n'
import { ApiError } from '@/api'
import { useAuthStore } from '@/stores/auth'
import { useNotificationsStore } from '@/stores/notifications'
import { THEME_OPTIONS, usePreferencesStore, type PreferencesUpdate } from '@/stores/preferences'
import { COLOR_THEMES } from '@/themes'
import { UI_SCALE_ICONS, UI_SCALES, uiScaleFactor } from '@/uiScale'
import { DATE_FORMATS, TIME_FORMATS } from '@/dateFormat'
import {
  CURRENCIES,
  CURRENCY_DISPLAYS,
  currencyInfo,
  MAX_PERCENT_PLACES,
  MIN_PERCENT_PLACES,
  NUMBER_FORMATS,
  type NumberFormat,
} from '@/numberFormat'
import { useDateFormat } from '@/composables/useDateFormat'
import SettingRow from '@/components/SettingRow.vue'
import { WEB_SEARCH_ENGINES, type WebSearchEngine } from '@/webSearch'

/** The search engines offered for "Search the Internet" */
const WEB_SEARCH_OPTIONS = Object.entries(WEB_SEARCH_ENGINES).map(([value, engine]) => ({
  value: value as WebSearchEngine,
  title: engine.name,
}))

/** 1, 2… 5 decimal places of percentages */
const PERCENT_PLACES = Array.from(
  { length: MAX_PERCENT_PLACES - MIN_PERCENT_PLACES + 1 },
  (_, i) => MIN_PERCENT_PLACES + i,
)

const { t, locale } = useI18n()
const preferences = usePreferencesStore()
const auth = useAuthStore()
const notifications = useNotificationsStore()

const saving = ref(false)

const THEMES = THEME_OPTIONS

// Tabs: the open one is kept in the address (?tab=), so a link can open it
type Tab = 'region' | 'appearance' | 'smartTools'
const TABS: readonly Tab[] = ['region', 'appearance', 'smartTools']
const route = useRoute()
const router = useRouter()
const tab = computed<Tab>({
  get: () => {
    const value = route.query.tab
    return (TABS as readonly unknown[]).includes(value) ? (value as Tab) : 'region'
  },
  set: (value) => void router.replace({ query: { ...route.query, tab: value } }),
})

// The user's currency: chosen by name or code; its symbol and code come from it
const currencies = computed(() =>
  CURRENCIES.map((code) => {
    const info = currencyInfo(code, locale.value)
    return { ...info, title: `${info.name} (${info.code})` }
  }),
)
const currency = computed(() => currencyInfo(preferences.currency, locale.value))

/** "By the Language", or the format itself ("1.234,56") */
const numberFormatLabel = (format: NumberFormat) =>
  format === 'auto'
    ? t('settings.numberFormats.auto')
    : { dot_comma: '1.234,56', comma_dot: '1,234.56', space_comma: '1 234,56' }[format]

// Smart Tools: the negligible threshold of the automatic scope (0–100 %), saved when left
const threshold = ref(toInputNumber(preferences.scopeThreshold, locale.value))
watch(
  () => preferences.scopeThreshold,
  (value) => (threshold.value = toInputNumber(value, locale.value)),
)
const thresholdValue = () => normalizeDecimal(threshold.value)
const thresholdRule = () => {
  const value = Number(thresholdValue())
  return (
    (threshold.value.trim() !== '' && value >= 0 && value <= 100) ||
    t('settings.smartTools.scopeThresholdRule')
  )
}
function saveThreshold() {
  if (thresholdRule() !== true) return
  const value = thresholdValue()
  if (Number(value) !== Number(preferences.scopeThreshold)) save({ scope_threshold: value })
}

// Date and time: an example with the formats chosen (now)
const { d } = useDateFormat()
const now = new Date()

/** The scale "Automatic" gives in this window now ("88%") */
const autoPercent = () => Math.round(uiScaleFactor('auto', window.innerWidth) * 100)

// Photo search: the SearXNG address, saved when left; "Test" tries it without saving
const searxngUrl = ref(preferences.searxngUrl)
watch(
  () => preferences.searxngUrl,
  (value) => (searxngUrl.value = value),
)
const searxngErrors = ref<string[]>([])
const searxngTesting = ref(false)
const searxngTest = ref<{ ok: boolean; text: string } | null>(null)

function apiMessage(error: unknown, fallback: string) {
  if (error instanceof ApiError) {
    const messages = error.fieldErrors().searxng_url
    if (messages?.length) return messages.join(' ')
    if (error.message) return error.message
  }
  return fallback
}

async function saveSearxng() {
  const url = searxngUrl.value.trim()
  if (url === preferences.searxngUrl) return
  saving.value = true
  try {
    await preferences.save({ searxng_url: url })
    notifications.notify(t('settings.saved'))
  } catch (error) {
    searxngErrors.value = [apiMessage(error, t('settings.saveError'))]
  } finally {
    saving.value = false
  }
}

async function testSearxng() {
  searxngTesting.value = true
  searxngTest.value = null
  try {
    const { results } = await preferences.testSearxng(searxngUrl.value.trim())
    searxngTest.value = { ok: true, text: t('system.searxng.testOk', results) }
  } catch (error) {
    searxngTest.value = { ok: false, text: apiMessage(error, t('system.searxng.testError')) }
  } finally {
    searxngTesting.value = false
  }
}

// How users are shown: an example with a made-up person
const nameExample = computed(() => {
  const first = t('system.userName.exampleFirst')
  const last = t('system.userName.exampleLast')
  if (preferences.userNameDisplay === 'username') return t('system.userName.exampleUsername')
  if (preferences.userNameDisplay === 'first_name') return first
  return preferences.fullNameOrder === 'last_first' ? `${last}, ${first}` : `${first} ${last}`
})

/** Names come formatted from the server: after a change, the top bar's name too */
async function saveNames(changes: PreferencesUpdate) {
  await save(changes)
  await auth.refresh().catch(() => {})
}

/** Every change is saved right away; the notice already shows in the newly chosen language. */
async function save(changes: PreferencesUpdate) {
  saving.value = true
  try {
    await preferences.save(changes)
    notifications.notify(t('settings.saved'))
  } catch {
    notifications.notify(t('settings.saveError'), 'error')
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <v-container fluid class="module-page settings-page">
    <h1 class="mb-1">{{ $t('settings.title') }}</h1>
    <p class="text-medium-emphasis mb-4">{{ $t('settings.subtitle') }}</p>

    <!-- Grouped in tabs (the open one is in the address: ?tab=) -->
    <v-tabs v-model="tab" color="primary" class="mb-5" data-testid="settings-sections">
      <v-tab value="region" prepend-icon="mdi-earth" data-testid="tab-region">
        {{ $t('settings.sections.region') }}
      </v-tab>
      <v-tab value="appearance" prepend-icon="mdi-palette-outline" data-testid="tab-appearance">
        {{ $t('settings.sections.appearance') }}
      </v-tab>
      <v-tab value="smartTools" prepend-icon="mdi-auto-fix" data-testid="tab-smart-tools">
        {{ $t('settings.sections.smartTools') }}
      </v-tab>
    </v-tabs>

    <v-window v-model="tab">
      <!-- Language and Region -->
      <v-window-item value="region" eager :transition="false" :reverse-transition="false">
        <div class="group-title">{{ $t('settings.language') }}</div>
        <v-card class="mb-6">
          <SettingRow
            :title="$t('settings.language')"
            :description="$t('settings.rows.languageHint')"
          >
            <v-select
              :model-value="preferences.language"
              :items="LANGUAGES"
              item-title="name"
              item-value="code"
              :disabled="saving"
              density="compact"
              hide-details
              class="control-wide"
              :aria-label="$t('settings.language')"
              data-testid="language-select"
              @update:model-value="save({ language: $event })"
            />
          </SettingRow>
        </v-card>

        <!-- How dates and times are written: by the language, or fixed -->
        <div class="group-title">{{ $t('settings.dateTime') }}</div>
        <v-card class="mb-6">
          <SettingRow
            :title="$t('settings.dateFormat')"
            :description="$t('settings.rows.dateFormatHint')"
          >
            <v-btn-toggle
              :model-value="preferences.dateFormat"
              mandatory
              divided
              variant="outlined"
              color="primary"
              density="comfortable"
              :disabled="saving"
              class="flex-wrap"
              data-testid="date-format"
              @update:model-value="save({ date_format: $event })"
            >
              <v-btn
                v-for="format in DATE_FORMATS"
                :key="format"
                :value="format"
                class="text-none"
                :data-testid="`date-format-${format}`"
              >
                {{ $t(`settings.dateFormats.${format}`) }}
              </v-btn>
            </v-btn-toggle>
          </SettingRow>
          <SettingRow :title="$t('settings.timeFormat')">
            <template #description>
              <span data-testid="date-time-example">
                {{ $t('settings.dateTimeExample', { example: d(now, 'dateTime') }) }}
              </span>
            </template>
            <v-btn-toggle
              :model-value="preferences.timeFormat"
              mandatory
              divided
              variant="outlined"
              color="primary"
              density="comfortable"
              :disabled="saving"
              data-testid="time-format"
              @update:model-value="save({ time_format: $event })"
            >
              <v-btn
                v-for="format in TIME_FORMATS"
                :key="format"
                :value="format"
                class="text-none"
                :data-testid="`time-format-${format}`"
              >
                {{ $t(`settings.timeFormats.${format}`) }}
              </v-btn>
            </v-btn-toggle>
          </SettingRow>
        </v-card>

        <!-- How numbers are written and the currency shown (src/numberFormat.ts) -->
        <div class="group-title">{{ $t('settings.numbers') }}</div>
        <v-card class="mb-6" data-testid="numbers">
          <SettingRow
            :title="$t('settings.numberFormat')"
            :description="$t('settings.rows.numberFormatHint')"
          >
            <v-btn-toggle
              :model-value="preferences.numberFormat"
              mandatory
              divided
              variant="outlined"
              color="primary"
              density="comfortable"
              :disabled="saving"
              class="flex-wrap"
              data-testid="number-format"
              @update:model-value="save({ number_format: $event })"
            >
              <v-btn
                v-for="format in NUMBER_FORMATS"
                :key="format"
                :value="format"
                class="text-none"
                :data-testid="`number-format-${format}`"
              >
                {{ numberFormatLabel(format) }}
              </v-btn>
            </v-btn-toggle>
          </SettingRow>
          <SettingRow :title="$t('settings.percentPlaces')">
            <template #description>
              <span data-testid="percent-example">
                {{ $t('settings.percentPlacesHint') }} {{ $n(12.3456789, 'percentValue') }}%
              </span>
            </template>
            <v-btn-toggle
              :model-value="preferences.percentPlaces"
              mandatory
              divided
              variant="outlined"
              color="primary"
              density="comfortable"
              :disabled="saving"
              data-testid="percent-places"
              @update:model-value="save({ percent_places: $event })"
            >
              <v-btn
                v-for="places in PERCENT_PLACES"
                :key="places"
                :value="places"
                class="text-none"
                :data-testid="`percent-places-${places}`"
              >
                {{ places }}
              </v-btn>
            </v-btn-toggle>
          </SettingRow>
          <SettingRow :title="$t('settings.currency')" :description="$t('settings.currencyHint')">
            <div class="d-flex flex-wrap align-center justify-end ga-2">
              <v-chip label variant="tonal" size="small" data-testid="currency-symbol">
                {{ $t('settings.currencySymbol') }}: {{ currency.symbol }}
              </v-chip>
              <v-chip label variant="tonal" size="small" data-testid="currency-code">
                {{ $t('settings.currencyCode') }}: {{ currency.code }}
              </v-chip>
              <v-autocomplete
                :model-value="preferences.currency"
                :items="currencies"
                item-title="title"
                item-value="code"
                :disabled="saving"
                density="compact"
                hide-details
                class="control-wide"
                :aria-label="$t('settings.currency')"
                data-testid="currency"
                @update:model-value="$event && save({ currency: $event })"
              />
            </div>
          </SettingRow>
          <SettingRow :title="$t('settings.currencyDisplay')">
            <template #description>
              {{ $t('settings.rows.currencyDisplayHint') }}
              <span data-testid="numbers-example">
                {{
                  $t('settings.numbersExample', {
                    example: formatMoney('1234567.89', preferences.currency, locale),
                  })
                }}
              </span>
            </template>
            <v-btn-toggle
              :model-value="preferences.currencyDisplay"
              mandatory
              divided
              variant="outlined"
              color="primary"
              density="comfortable"
              :disabled="saving"
              data-testid="currency-display"
              @update:model-value="save({ currency_display: $event })"
            >
              <v-btn
                v-for="shown in CURRENCY_DISPLAYS"
                :key="shown"
                :value="shown"
                class="text-none"
                :data-testid="`currency-display-${shown}`"
              >
                {{ $t(`settings.currencyDisplays.${shown}`, currency) }}
              </v-btn>
            </v-btn-toggle>
          </SettingRow>
        </v-card>
      </v-window-item>

      <!-- Appearance -->
      <v-window-item value="appearance" eager :transition="false" :reverse-transition="false">
        <div class="group-title">{{ $t('settings.appearance') }}</div>
        <v-card class="mb-6">
          <SettingRow :title="$t('settings.theme')" :description="$t('settings.rows.themeHint')">
            <v-btn-toggle
              :model-value="preferences.theme"
              mandatory
              divided
              variant="outlined"
              color="primary"
              density="comfortable"
              :disabled="saving"
              data-testid="theme-toggle"
              @update:model-value="save({ theme: $event })"
            >
              <v-btn
                v-for="item in THEMES"
                :key="item.value"
                :value="item.value"
                :prepend-icon="item.icon"
              >
                {{ $t(`settings.themes.${item.value}`) }}
              </v-btn>
            </v-btn-toggle>
          </SettingRow>
          <!-- Color theme: each one in a light and a dark version (the mode above) -->
          <SettingRow
            :title="$t('settings.colorTheme')"
            :description="$t('settings.rows.colorThemeHint')"
          >
            <template #below>
              <div class="d-flex flex-wrap ga-3" data-testid="color-themes">
                <v-card
                  v-for="colorTheme in COLOR_THEMES"
                  :key="colorTheme.id"
                  :variant="preferences.colorTheme === colorTheme.id ? 'outlined' : 'flat'"
                  :color="preferences.colorTheme === colorTheme.id ? 'primary' : undefined"
                  :class="{ 'color-theme--selected': preferences.colorTheme === colorTheme.id }"
                  class="color-theme pa-3"
                  width="240"
                  :disabled="saving"
                  :aria-pressed="preferences.colorTheme === colorTheme.id"
                  :data-testid="`color-theme-${colorTheme.id}`"
                  @click="save({ color_theme: colorTheme.id })"
                >
                  <div class="swatches d-flex rounded overflow-hidden mb-2" style="height: 32px">
                    <div
                      v-for="swatch in colorTheme.swatches"
                      :key="swatch"
                      class="flex-grow-1"
                      :style="{ background: swatch }"
                    />
                  </div>
                  <div class="d-flex align-center justify-space-between">
                    <div>
                      <div class="text-body-2 font-weight-medium">{{ colorTheme.name }}</div>
                      <div
                        class="text-caption text-medium-emphasis"
                        :style="{ fontFamily: `${colorTheme.fontFamily} !important` }"
                      >
                        Aa · {{ colorTheme.fontName }}
                      </div>
                    </div>
                    <v-icon
                      v-if="preferences.colorTheme === colorTheme.id"
                      icon="mdi-check-circle"
                      color="primary"
                      size="small"
                    />
                  </div>
                </v-card>
              </div>
            </template>
          </SettingRow>
          <!-- Size of the interface (text, spacing, fields): automatic by the window's width -->
          <SettingRow :title="$t('settings.uiScale')">
            <template #description>
              {{ $t('settings.uiScaleDescription') }}
              <span data-testid="ui-scale-hint">
                {{ $t('settings.uiScaleAutoHint', { percent: autoPercent() }) }}
              </span>
            </template>
            <v-btn-toggle
              :model-value="preferences.uiScale"
              mandatory
              divided
              variant="outlined"
              color="primary"
              density="comfortable"
              :disabled="saving"
              class="flex-wrap"
              data-testid="ui-scale-toggle"
              @update:model-value="save({ ui_scale: $event })"
            >
              <v-btn
                v-for="scale in UI_SCALES"
                :key="scale"
                :value="scale"
                :prepend-icon="UI_SCALE_ICONS[scale]"
                :data-testid="`ui-scale-${scale}`"
              >
                {{ $t(`settings.uiScales.${scale}`) }}
              </v-btn>
            </v-btn-toggle>
          </SettingRow>
        </v-card>

        <!-- How users are shown everywhere (each user's own; the server formats the names) -->
        <div class="group-title">{{ $t('system.userName.title') }}</div>
        <v-card class="mb-6" data-testid="user-name-display">
          <SettingRow :title="$t('system.userName.show')" :description="$t('system.userName.hint')">
            <v-btn-toggle
              :model-value="preferences.userNameDisplay"
              mandatory
              divided
              variant="outlined"
              color="primary"
              density="comfortable"
              :disabled="saving"
              class="flex-wrap"
              data-testid="name-display"
              @update:model-value="saveNames({ user_name_display: $event })"
            >
              <v-btn value="username" class="text-none" data-testid="name-display-username">
                {{ $t('system.userName.options.username') }}
              </v-btn>
              <v-btn value="first_name" class="text-none" data-testid="name-display-first_name">
                {{ $t('system.userName.options.firstName') }}
              </v-btn>
              <v-btn value="full_name" class="text-none" data-testid="name-display-full_name">
                {{ $t('system.userName.options.fullName') }}
              </v-btn>
            </v-btn-toggle>
          </SettingRow>
          <SettingRow
            :title="$t('system.userName.order')"
            :disabled="preferences.userNameDisplay === 'username'"
            child
          >
            <template #description>
              {{ $t('system.userName.orderHint') }}
              <span data-testid="name-example">
                {{ $t('system.userName.example') }} {{ nameExample }}
              </span>
            </template>
            <v-btn-toggle
              :model-value="preferences.fullNameOrder"
              mandatory
              divided
              variant="outlined"
              color="primary"
              density="comfortable"
              :disabled="saving || preferences.userNameDisplay === 'username'"
              data-testid="name-order"
              @update:model-value="saveNames({ full_name_order: $event })"
            >
              <v-btn value="first_last" class="text-none" data-testid="name-order-first_last">
                {{ $t('system.userName.orders.firstLast') }}
              </v-btn>
              <v-btn value="last_first" class="text-none" data-testid="name-order-last_first">
                {{ $t('system.userName.orders.lastFirst') }}
              </v-btn>
            </v-btn-toggle>
          </SettingRow>
        </v-card>
      </v-window-item>

      <!-- Smart Tools: conveniences of the interface, each turned on or off (src/smartTools.ts) -->
      <v-window-item value="smartTools" eager :transition="false" :reverse-transition="false">
        <div class="group-title">{{ $t('settings.smartTools.title') }}</div>
        <v-card class="mb-6" data-testid="smart-tools">
          <SettingRow
            :title="$t('settings.smartTools.selectOnFocus')"
            :description="$t('settings.smartTools.selectOnFocusHint')"
          >
            <v-switch
              :model-value="preferences.selectOnFocus"
              color="primary"
              inset
              hide-details
              density="compact"
              :disabled="saving"
              :aria-label="$t('settings.smartTools.selectOnFocus')"
              data-testid="select-on-focus"
              @update:model-value="save({ select_on_focus: !!$event })"
            />
          </SettingRow>
          <SettingRow
            :title="$t('settings.smartTools.autoScope')"
            :description="$t('settings.smartTools.autoScopeHint')"
          >
            <v-switch
              :model-value="preferences.autoScope"
              color="primary"
              inset
              hide-details
              density="compact"
              :disabled="saving"
              :aria-label="$t('settings.smartTools.autoScope')"
              data-testid="auto-scope"
              @update:model-value="save({ auto_scope: !!$event })"
            />
          </SettingRow>
          <SettingRow
            :disabled="!preferences.autoScope"
            :title="$t('settings.smartTools.scopeThreshold')"
            :description="$t('settings.smartTools.scopeThresholdHint')"
            child
          >
            <v-text-field
              v-model="threshold"
              suffix="%"
              inputmode="decimal"
              :rules="[thresholdRule]"
              :disabled="saving || !preferences.autoScope"
              density="compact"
              hide-details="auto"
              class="control-narrow"
              :aria-label="$t('settings.smartTools.scopeThreshold')"
              data-testid="scope-threshold"
              @blur="saveThreshold"
              @keydown.enter="saveThreshold"
            />
          </SettingRow>
          <!-- A button inside some text fields searches the Internet (src/webSearch.ts) -->
          <SettingRow
            :title="$t('settings.webSearch.title')"
            :description="$t('settings.webSearch.description')"
          >
            <v-switch
              :model-value="preferences.webSearch"
              color="primary"
              inset
              hide-details
              density="compact"
              :disabled="saving"
              :aria-label="$t('settings.webSearch.title')"
              data-testid="web-search-switch"
              @update:model-value="save({ web_search: !!$event })"
            />
          </SettingRow>
          <SettingRow
            :disabled="!preferences.webSearch"
            :title="$t('settings.webSearch.engine')"
            :description="$t('settings.rows.engineHint')"
            child
          >
            <v-select
              :model-value="preferences.webSearchEngine"
              :items="WEB_SEARCH_OPTIONS"
              :disabled="saving || !preferences.webSearch"
              density="compact"
              hide-details
              class="control-wide"
              :aria-label="$t('settings.webSearch.engine')"
              data-testid="web-search-engine"
              @update:model-value="save({ web_search_engine: $event })"
            />
          </SettingRow>
          <!-- Part of Internet Search: photos of the assets through SearXNG (Average Prices) -->
          <SettingRow :disabled="!preferences.webSearch" :title="$t('system.searxng.url')" child>
            <template #description>
              {{ $t('settings.rows.photoSearchHint') }} {{ $t('settings.rows.searxngHint') }}
              <span
                v-if="searxngTest"
                :class="searxngTest.ok ? 'text-success' : 'text-error'"
                data-testid="searxng-test-result"
              >
                {{ searxngTest.text }}
              </span>
            </template>
            <div class="d-flex align-center ga-2">
              <v-text-field
                v-model="searxngUrl"
                :placeholder="$t('system.searxng.urlHint')"
                :error-messages="searxngErrors"
                :disabled="saving || !preferences.webSearch"
                density="compact"
                hide-details="auto"
                class="control-wide"
                :aria-label="$t('system.searxng.url')"
                data-testid="searxng-url"
                @update:model-value="searxngErrors = []"
                @blur="saveSearxng"
                @keydown.enter="saveSearxng"
              />
              <v-btn
                variant="tonal"
                color="primary"
                :loading="searxngTesting"
                :disabled="!searxngUrl.trim() || !preferences.webSearch"
                data-testid="searxng-test"
                @click="testSearxng"
              >
                {{ $t('system.searxng.test') }}
              </v-btn>
            </div>
          </SettingRow>
        </v-card>
      </v-window-item>
    </v-window>
  </v-container>
</template>

<style scoped>
/* A small caption over each card (the group of settings) */
.group-title {
  font-size: 0.75rem;
  font-weight: 600;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: rgba(var(--v-theme-on-surface), var(--v-medium-emphasis-opacity));
  margin: 0 0 8px 4px;
}
.control-wide {
  width: 300px;
  max-width: 100%;
}
.control-narrow {
  width: 140px;
}
.color-theme {
  cursor: pointer;
  border: 1px solid rgba(var(--v-border-color), var(--v-border-opacity));
}
/* Outlined so a swatch the color of the card still shows */
.swatches {
  border: 1px solid rgba(var(--v-border-color), var(--v-border-opacity));
}
.color-theme--selected {
  border-width: 2px;
}
</style>
