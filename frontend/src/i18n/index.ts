/**
 * UI internationalization (vue-i18n).
 *
 * To add a language:
 *   1. create `locales/<code>.ts` typed with `Messages`;
 *   2. add it to LANGUAGES and to `messages` below (together with Vuetify's translations);
 *   3. add the same code to LANGUAGES in the backend (config/settings.py).
 * Codes follow Django's format (lowercase, e.g. 'pt-br').
 */
import type { App } from 'vue'
import { createI18n } from 'vue-i18n'
import { formatNumber, NAMED_NUMBER_FORMATS, type NumberKey } from '@/numberFormat'
import { en as vuetifyEn, es as vuetifyEs, pt as vuetifyPt } from 'vuetify/locale'

import en, { type Messages } from './locales/en'
import es from './locales/es'
import ptBR from './locales/pt-br'

export const LANGUAGES = [
  { code: 'en', name: 'English' },
  { code: 'pt-br', name: 'Português (Brasil)' },
  { code: 'es', name: 'Español' },
] as const

export type Language = (typeof LANGUAGES)[number]['code']

export const DEFAULT_LANGUAGE: Language = 'en'

const STORAGE_KEY = 'horizon.language'

const messages = {
  en: { ...en, $vuetify: vuetifyEn },
  'pt-br': { ...ptBR, $vuetify: vuetifyPt },
  es: { ...es, $vuetify: vuetifyEs },
} satisfies Record<Language, Messages & { $vuetify: unknown }>

/** Same formats for every language; Intl adapts separators and month names. */
const datetimeFormats = {
  short: { year: 'numeric', month: '2-digit', day: '2-digit' },
  long: { year: 'numeric', month: 'long', day: 'numeric' },
  dateTime: {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  },
} as const

// Numbers follow the user's number format (src/numberFormat.ts)
const numberFormats = NAMED_NUMBER_FORMATS

export function isSupportedLanguage(code: string): code is Language {
  return LANGUAGES.some((l) => l.code === code)
}

/** Map a browser language code (e.g. 'pt-BR', 'en-US') to a supported one. */
export function normalizeLanguage(code: string): Language | null {
  const lower = code.toLowerCase()
  if (isSupportedLanguage(lower)) return lower
  const base = lower.split('-')[0]
  return LANGUAGES.find((l) => l.code.split('-')[0] === base)?.code ?? null
}

/** Initial language: last one picked in this browser, else the browser's, else the default. */
export function detectLanguage(): Language {
  try {
    const stored = localStorage.getItem(STORAGE_KEY)
    if (stored && isSupportedLanguage(stored)) return stored
  } catch {
    /* storage unavailable (private mode, blocked by the browser) */
  }
  for (const code of navigator.languages ?? [navigator.language]) {
    const language = normalizeLanguage(code)
    if (language) return language
  }
  return DEFAULT_LANGUAGE
}

const base = createI18n({
  legacy: false,
  locale: detectLanguage(),
  fallbackLocale: DEFAULT_LANGUAGE,
  messages,
  datetimeFormats: Object.fromEntries(LANGUAGES.map((l) => [l.code, datetimeFormats])),
  numberFormats: Object.fromEntries(LANGUAGES.map((l) => [l.code, numberFormats])),
})

/**
 * vue-i18n, with `$n` writing numbers in the user's number format (Settings): the same named
 * formats, separators from `numberLocale` (src/numberFormat.ts).
 */
const baseInstall = base.install.bind(base) as (app: App, ...options: unknown[]) => void
export const i18n = Object.assign(base, {
  install(app: App, ...options: unknown[]) {
    baseInstall(app, ...options)
    app.config.globalProperties.$n = ((value: number, key?: NumberKey) =>
      formatNumber(value, key, base.global.locale.value)) as typeof app.config.globalProperties.$n
  },
})

export function currentLanguage(): Language {
  const current = i18n.global.locale.value
  return isSupportedLanguage(current) ? current : DEFAULT_LANGUAGE
}

/** Switch the UI language and remember it in this browser (also used before login). */
export function setLanguage(language: Language) {
  i18n.global.locale.value = language
  document.documentElement.lang = language
  try {
    localStorage.setItem(STORAGE_KEY, language)
  } catch {
    /* storage unavailable */
  }
}

document.documentElement.lang = currentLanguage()

// Editor autocompletion for translation keys. Whether the keys used in code exist is checked
// by src/i18n/__tests__/i18n.spec.ts (type-check does not catch it in templates).
declare module 'vue-i18n' {
  // eslint-disable-next-line @typescript-eslint/no-empty-object-type
  export interface DefineLocaleMessage extends Messages {}
}
