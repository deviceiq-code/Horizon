<script setup lang="ts">
/**
 * The user's own settings (language, mode, color theme, interface size, date and time formats),
 * saved to their account. Global
 * settings are in Administration → System Settings.
 */
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { LANGUAGES } from '@/i18n'
import { useNotificationsStore } from '@/stores/notifications'
import { THEME_OPTIONS, usePreferencesStore, type PreferencesUpdate } from '@/stores/preferences'
import { COLOR_THEMES } from '@/themes'
import { UI_SCALE_ICONS, UI_SCALES, uiScaleFactor } from '@/uiScale'
import { DATE_FORMATS, TIME_FORMATS } from '@/dateFormat'
import { useDateFormat } from '@/composables/useDateFormat'

const { t } = useI18n()
const preferences = usePreferencesStore()
const notifications = useNotificationsStore()

const saving = ref(false)

const THEMES = THEME_OPTIONS

// Date and time: an example with the formats chosen (now)
const { d } = useDateFormat()
const now = new Date()

/** The scale "Automatic" gives in this window now ("88%") */
const autoPercent = () => Math.round(uiScaleFactor('auto', window.innerWidth) * 100)

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
  <v-container style="max-width: 900px">
    <h1 class="text-h5 mb-1">{{ $t('settings.title') }}</h1>

    <p class="text-medium-emphasis mb-4">{{ $t('settings.subtitle') }}</p>

    <v-card class="mb-4">
      <v-card-item prepend-icon="mdi-translate">
        <v-card-title>{{ $t('settings.language') }}</v-card-title>
        <v-card-subtitle>{{ $t('settings.languageDescription') }}</v-card-subtitle>
      </v-card-item>
      <v-card-text>
        <v-select
          :model-value="preferences.language"
          :items="LANGUAGES"
          item-title="name"
          item-value="code"
          :label="$t('settings.language')"
          :disabled="saving"
          hide-details
          style="max-width: 360px"
          data-testid="language-select"
          @update:model-value="save({ language: $event })"
        />
      </v-card-text>
    </v-card>

    <v-card>
      <v-card-item prepend-icon="mdi-palette-outline">
        <v-card-title>{{ $t('settings.appearance') }}</v-card-title>
        <v-card-subtitle>{{ $t('settings.themeDescription') }}</v-card-subtitle>
      </v-card-item>
      <v-card-text>
        <div class="text-body-2 mb-2">{{ $t('settings.theme') }}</div>
        <v-btn-toggle
          :model-value="preferences.theme"
          mandatory
          divided
          variant="outlined"
          color="primary"
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

        <!-- Color theme: each one in a light and a dark version (the mode above) -->
        <div class="text-body-2 mt-6 mb-2">{{ $t('settings.colorTheme') }}</div>
        <div class="d-flex flex-wrap ga-3" data-testid="color-themes">
          <v-card
            v-for="colorTheme in COLOR_THEMES"
            :key="colorTheme.id"
            :variant="preferences.colorTheme === colorTheme.id ? 'outlined' : 'flat'"
            :color="preferences.colorTheme === colorTheme.id ? 'primary' : undefined"
            :class="{ 'color-theme--selected': preferences.colorTheme === colorTheme.id }"
            class="color-theme pa-3"
            width="260"
            :disabled="saving"
            :aria-pressed="preferences.colorTheme === colorTheme.id"
            :data-testid="`color-theme-${colorTheme.id}`"
            @click="save({ color_theme: colorTheme.id })"
          >
            <div class="swatches d-flex rounded overflow-hidden mb-2" style="height: 36px">
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
      </v-card-text>
    </v-card>

    <!-- Size of the interface (text, spacing, fields): automatic by the window's width -->
    <v-card class="mt-4">
      <v-card-item prepend-icon="mdi-magnify-plus-outline">
        <v-card-title>{{ $t('settings.uiScale') }}</v-card-title>
        <v-card-subtitle>{{ $t('settings.uiScaleDescription') }}</v-card-subtitle>
      </v-card-item>
      <v-card-text>
        <v-btn-toggle
          :model-value="preferences.uiScale"
          mandatory
          divided
          variant="outlined"
          color="primary"
          :disabled="saving"
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
        <div class="text-caption text-medium-emphasis mt-2" data-testid="ui-scale-hint">
          {{ $t('settings.uiScaleAutoHint', { percent: autoPercent() }) }}
        </div>
      </v-card-text>
    </v-card>

    <!-- How dates and times are written: by the language, or fixed -->
    <v-card class="mt-4">
      <v-card-item prepend-icon="mdi-calendar-clock-outline">
        <v-card-title>{{ $t('settings.dateTime') }}</v-card-title>
        <v-card-subtitle>{{ $t('settings.dateTimeDescription') }}</v-card-subtitle>
      </v-card-item>
      <v-card-text>
        <div class="text-body-2 mb-2">{{ $t('settings.dateFormat') }}</div>
        <v-btn-toggle
          :model-value="preferences.dateFormat"
          mandatory
          divided
          variant="outlined"
          color="primary"
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

        <div class="text-body-2 mt-5 mb-2">{{ $t('settings.timeFormat') }}</div>
        <v-btn-toggle
          :model-value="preferences.timeFormat"
          mandatory
          divided
          variant="outlined"
          color="primary"
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

        <div class="text-body-2 text-medium-emphasis mt-4" data-testid="date-time-example">
          {{ $t('settings.dateTimeExample', { example: d(now, 'dateTime') }) }}
        </div>
      </v-card-text>
    </v-card>
  </v-container>
</template>

<style scoped>
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
