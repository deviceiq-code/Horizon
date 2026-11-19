import { ref } from 'vue'
import { defineStore } from 'pinia'
import { api } from '@/api'
import { currentLanguage, isSupportedLanguage, setLanguage, type Language } from '@/i18n'

export type Theme = 'light' | 'dark' | 'system'

/** User preferences as returned by the API (/api/auth/preferences/). */
export interface Preferences {
  language: string
  theme: Theme
  updated_at: string
}

export type PreferencesUpdate = Partial<{ language: Language; theme: Theme }>

const THEMES: readonly Theme[] = ['light', 'dark', 'system']
const THEME_STORAGE_KEY = 'horizon.theme'

function readStoredTheme(): Theme {
  try {
    const stored = localStorage.getItem(THEME_STORAGE_KEY)
    if (stored && (THEMES as readonly string[]).includes(stored)) return stored as Theme
  } catch {
    /* storage unavailable */
  }
  return 'system'
}

function storeTheme(theme: Theme) {
  try {
    localStorage.setItem(THEME_STORAGE_KEY, theme)
  } catch {
    /* storage unavailable */
  }
}

/**
 * Language and theme in use. Values saved to the account (database) win;
 * a copy is kept in the browser so the login page already opens the right way.
 */
export const usePreferencesStore = defineStore('preferences', () => {
  const language = ref<Language>(currentLanguage())
  const theme = ref<Theme>(readStoredTheme())

  /** Apply preferences to the UI without saving them to the account. */
  function apply(p: { language?: string; theme?: Theme }) {
    if (p.language && isSupportedLanguage(p.language)) {
      language.value = p.language
      setLanguage(p.language)
    }
    if (p.theme && THEMES.includes(p.theme)) {
      theme.value = p.theme
      storeTheme(p.theme)
    }
  }

  /** Apply immediately and save to the account; if the API fails, roll back and rethrow. */
  async function save(changes: PreferencesUpdate) {
    const previous = { language: language.value, theme: theme.value }
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

  return { language, theme, apply, save }
})
