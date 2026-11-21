import { ref } from 'vue'
import { defineStore } from 'pinia'
import { api } from '@/api'
import { currentLanguage, isSupportedLanguage, setLanguage, type Language } from '@/i18n'
import { DEFAULT_COLOR_THEME, isColorTheme } from '@/themes'
import { isUiScale, type UiScale } from '@/uiScale'

export type Theme = 'light' | 'dark' | 'system'

/** User preferences as returned by the API (/api/auth/preferences/). */
export interface Preferences {
  language: string
  theme: Theme
  /** Color theme id (src/themes.ts) */
  color_theme: string
  /** Size of the interface (src/uiScale.ts); "auto" follows the window's width */
  ui_scale: UiScale
  updated_at: string
}

export type PreferencesUpdate = Partial<{
  language: Language
  theme: Theme
  color_theme: string
  ui_scale: UiScale
}>

const THEMES: readonly Theme[] = ['light', 'dark', 'system']

/** The themes offered to users (Settings and the user menu), with their icons. */
export const THEME_OPTIONS: readonly { value: Theme; icon: string }[] = [
  { value: 'light', icon: 'mdi-white-balance-sunny' },
  { value: 'dark', icon: 'mdi-weather-night' },
  { value: 'system', icon: 'mdi-theme-light-dark' },
]
const THEME_STORAGE_KEY = 'horizon.theme'
const COLOR_THEME_STORAGE_KEY = 'horizon.colorTheme'
const UI_SCALE_STORAGE_KEY = 'horizon.uiScale'

function readStoredUiScale(): UiScale {
  try {
    const stored = localStorage.getItem(UI_SCALE_STORAGE_KEY)
    if (isUiScale(stored)) return stored
  } catch {
    /* storage unavailable */
  }
  return 'auto'
}

function readStoredColorTheme(): string {
  try {
    const stored = localStorage.getItem(COLOR_THEME_STORAGE_KEY)
    if (isColorTheme(stored)) return stored as string
  } catch {
    /* storage unavailable */
  }
  return DEFAULT_COLOR_THEME
}

function readStoredTheme(): Theme {
  try {
    const stored = localStorage.getItem(THEME_STORAGE_KEY)
    if (stored && (THEMES as readonly string[]).includes(stored)) return stored as Theme
  } catch {
    /* storage unavailable */
  }
  return 'system'
}

function store(key: string, value: string) {
  try {
    localStorage.setItem(key, value)
  } catch {
    /* storage unavailable */
  }
}

/**
 * Language, mode (light/dark/system), color theme and interface size in use. Values saved to the account (database) win;
 * a copy is kept in the browser so the login page already opens the right way.
 */
export const usePreferencesStore = defineStore('preferences', () => {
  const language = ref<Language>(currentLanguage())
  const theme = ref<Theme>(readStoredTheme())
  const colorTheme = ref<string>(readStoredColorTheme())
  const uiScale = ref<UiScale>(readStoredUiScale())

  /** Apply preferences to the UI without saving them to the account. */
  function apply(p: { language?: string; theme?: Theme; color_theme?: string; ui_scale?: string }) {
    if (p.language && isSupportedLanguage(p.language)) {
      language.value = p.language
      setLanguage(p.language)
    }
    if (p.theme && THEMES.includes(p.theme)) {
      theme.value = p.theme
      store(THEME_STORAGE_KEY, p.theme)
    }
    if (p.color_theme && isColorTheme(p.color_theme)) {
      colorTheme.value = p.color_theme
      store(COLOR_THEME_STORAGE_KEY, p.color_theme)
    }
    if (isUiScale(p.ui_scale)) {
      uiScale.value = p.ui_scale
      store(UI_SCALE_STORAGE_KEY, p.ui_scale)
    }
  }

  /** Apply immediately and save to the account; if the API fails, roll back and rethrow. */
  async function save(changes: PreferencesUpdate) {
    const previous = {
      language: language.value,
      theme: theme.value,
      color_theme: colorTheme.value,
      ui_scale: uiScale.value,
    }
    apply(changes)
    try {
      const saved = await api<Preferences>('/auth/preferences/', {
        method: 'PATCH',
        body: JSON.stringify(changes),
      })
      apply(saved)
    } catch (error) {
      apply(previous)
      throw error
    }
  }

  return { language, theme, colorTheme, uiScale, apply, save }
})
