import { ref, toRaw } from 'vue'
import { defineStore } from 'pinia'
import { api } from '@/api'
import { currentLanguage, isSupportedLanguage, setLanguage, type Language } from '@/i18n'
import { DEFAULT_COLOR_THEME, isColorTheme } from '@/themes'
import { isUiScale, type UiScale } from '@/uiScale'
import { isWebSearchEngine, type WebSearchEngine } from '@/webSearch'
import { isDateFormat, isTimeFormat, type DateFormat, type TimeFormat } from '@/dateFormat'
import {
  isCurrency,
  isCurrencyDisplay,
  isNumberFormat,
  isPercentPlaces,
  numberSettings,
  type Currency,
  type CurrencyDisplay,
  type NumberFormat,
} from '@/numberFormat'

export type Theme = 'light' | 'dark' | 'system'
/** How users are shown to this user (the API already sends names formatted this way) */
export type UserNameDisplay = 'username' | 'first_name' | 'full_name'
export type FullNameOrder = 'first_last' | 'last_first'
const USER_NAME_DISPLAYS: readonly UserNameDisplay[] = ['username', 'first_name', 'full_name']
const FULL_NAME_ORDERS: readonly FullNameOrder[] = ['first_last', 'last_first']

/** User preferences as returned by the API (/api/auth/preferences/). */
/** How far back the Home's journal looks (days; 1 = today) — `accounts.models.JournalPeriod` */
export const JOURNAL_PERIODS = [1, 7, 30] as const
export type JournalDays = (typeof JOURNAL_PERIODS)[number]
/** How the Home's two journals are placed — `accounts.models.JournalLayout` */
export const JOURNAL_LAYOUTS = ['vertical', 'horizontal'] as const
export type JournalLayout = (typeof JOURNAL_LAYOUTS)[number]
const isJournalLayout = (v: unknown): v is JournalLayout =>
  JOURNAL_LAYOUTS.includes(v as JournalLayout)
const isJournalDays = (v: unknown): v is JournalDays => JOURNAL_PERIODS.includes(v as JournalDays)

export interface Preferences {
  language: string
  theme: Theme
  /** Color theme id (src/themes.ts) */
  color_theme: string
  /** Size of the interface (src/uiScale.ts); "auto" follows the window's width */
  ui_scale: UiScale
  /** How dates and times are written (src/dateFormat.ts); "auto" follows the language */
  date_format: DateFormat
  time_format: TimeFormat
  /** How numbers are written and the currency shown (src/numberFormat.ts) */
  number_format: NumberFormat
  /** Decimal places of every percentage shown (1–5) */
  percent_places: number
  /** The user's currency (ISO 4217): its symbol and code; values keep their own currency */
  currency: Currency
  currency_display: CurrencyDisplay
  /** How the user left the interface (side menu, grids' filters…): follows them anywhere */
  ui_state: UiState
  /** How users are shown everywhere (top bar, "created by", history…) */
  user_name_display: UserNameDisplay
  full_name_order: FullNameOrder
  /** Smart Tools, part of Internet Search: photos of the assets found through this SearXNG */
  searxng_url: string
  /** Smart Tools: a button in some text fields searches the Internet, with this engine */
  web_search: boolean
  web_search_engine: WebSearchEngine
  /** Smart Tools: entering a text field selects its content (src/smartTools.ts) */
  select_on_focus: boolean
  /** Smart Tools: words typed in forms written as the shared dictionary says (wordDictionary.ts) */
  word_dictionary: boolean
  /** Smart Tools: text typed in forms without extra spaces (tidySpaces.ts) */
  trim_spaces: boolean
  /** The Home's journal: its two parts shown or not */
  show_data_journal: boolean
  show_system_journal: boolean
  /** The Home's two journals: one under the other or side by side */
  journal_layout: JournalLayout
  /** The Home's journal: today (1) or the last 7 or 30 days */
  journal_days: JournalDays
  /** Smart Tools: eFMV scenarios' scope written from their assets; negligible below (%) */
  auto_scope: boolean
  scope_threshold: string
  updated_at: string
}

export type PreferencesUpdate = Partial<{
  language: Language
  theme: Theme
  color_theme: string
  ui_scale: UiScale
  date_format: DateFormat
  time_format: TimeFormat
  number_format: NumberFormat
  percent_places: number
  currency: Currency
  currency_display: CurrencyDisplay
  ui_state: UiState
  user_name_display: UserNameDisplay
  full_name_order: FullNameOrder
  searxng_url: string
  web_search: boolean
  web_search_engine: WebSearchEngine
  select_on_focus: boolean
  word_dictionary: boolean
  trim_spaces: boolean
  show_data_journal: boolean
  show_system_journal: boolean
  journal_layout: JournalLayout
  journal_days: JournalDays
  auto_scope: boolean
  scope_threshold: string
}>

/** The interface's own state kept with the account (not interpreted by the API). */
export interface UiState {
  /** Side menu open or closed, on wide and on narrow screens */
  sideMenu?: { wide?: 'open' | 'collapsed'; narrow?: 'open' | 'collapsed' }
  /** Grids whose filter row is shown, by the grid's key */
  filters?: Record<string, boolean>
  /** Movement reads the location where the object is first (RN-19) */
  readOrigin?: boolean
  /** The newest version the user saw in the Home's journal (newer ones show "New") */
  lastSeenRelease?: string
}

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

const SELECT_ON_FOCUS_STORAGE_KEY = 'horizon.selectOnFocus'
const AUTO_SCOPE_STORAGE_KEY = 'horizon.autoScope'
const SCOPE_THRESHOLD_STORAGE_KEY = 'horizon.scopeThreshold'
const DATE_FORMAT_STORAGE_KEY = 'horizon.dateFormat'
const TIME_FORMAT_STORAGE_KEY = 'horizon.timeFormat'
const NUMBER_FORMAT_STORAGE_KEY = 'horizon.numberFormat'
const CURRENCY_DISPLAY_STORAGE_KEY = 'horizon.currencyDisplay'
const CURRENCY_STORAGE_KEY = 'horizon.currency'
const PERCENT_PLACES_STORAGE_KEY = 'horizon.percentPlaces'
const WEB_SEARCH_STORAGE_KEY = 'horizon.webSearchEngine'
const WEB_SEARCH_ON_STORAGE_KEY = 'horizon.webSearch'

function readStored<T extends string>(key: string, valid: (v: unknown) => v is T, fallback: T): T {
  try {
    const stored = localStorage.getItem(key)
    if (valid(stored)) return stored
  } catch {
    /* storage unavailable */
  }
  return fallback
}

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
  // Light by default (Emerald Slate in light mode)
  return 'light'
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
  const dateFormat = ref<DateFormat>(readStored(DATE_FORMAT_STORAGE_KEY, isDateFormat, 'auto'))
  const timeFormat = ref<TimeFormat>(readStored(TIME_FORMAT_STORAGE_KEY, isTimeFormat, 'auto'))
  const numberFormat = ref<NumberFormat>(
    readStored(NUMBER_FORMAT_STORAGE_KEY, isNumberFormat, 'auto'),
  )
  const currency = ref<Currency>(readStored(CURRENCY_STORAGE_KEY, isCurrency, 'BRL'))
  const currencyDisplay = ref<CurrencyDisplay>(
    readStored(CURRENCY_DISPLAY_STORAGE_KEY, isCurrencyDisplay, 'symbol'),
  )
  const percentPlaces = ref(
    Number(
      readStored(PERCENT_PLACES_STORAGE_KEY, (v): v is string => isPercentPlaces(Number(v)), '2'),
    ),
  )
  numberSettings.percentPlaces = percentPlaces.value
  numberSettings.format = numberFormat.value
  numberSettings.currency = currencyDisplay.value
  // Only with the account: the server formats the names
  const userNameDisplay = ref<UserNameDisplay>('full_name')
  const fullNameOrder = ref<FullNameOrder>('first_last')
  // Only with the account
  const searxngUrl = ref('')
  const webSearch = ref(
    readStored(WEB_SEARCH_ON_STORAGE_KEY, (v): v is string => v === 'false', 'true') !== 'false',
  )
  const webSearchEngine = ref<WebSearchEngine>(
    readStored(WEB_SEARCH_STORAGE_KEY, isWebSearchEngine, 'google'),
  )
  // Only with the account (nothing kept in the browser): empty until signed in
  const uiState = ref<UiState>({})
  // On unless turned off (also before signing in)
  const selectOnFocus = ref(
    readStored(SELECT_ON_FOCUS_STORAGE_KEY, (v): v is string => v === 'false', 'true') !== 'false',
  )
  // On unless turned off (only with the account)
  const wordDictionary = ref(true)
  const trimSpaces = ref(true)
  const journalDays = ref<JournalDays>(7)
  const showDataJournal = ref(true)
  const showSystemJournal = ref(true)
  const journalLayout = ref<JournalLayout>('vertical')
  const autoScope = ref(
    readStored(AUTO_SCOPE_STORAGE_KEY, (v): v is string => v === 'false', 'true') !== 'false',
  )
  const scopeThreshold = ref(
    readStored(
      SCOPE_THRESHOLD_STORAGE_KEY,
      (v): v is string => typeof v === 'string' && /^\d+(\.\d+)?$/.test(v),
      '5.00',
    ),
  )

  /** Apply preferences to the UI without saving them to the account. */
  function apply(p: {
    language?: string
    theme?: Theme
    color_theme?: string
    ui_scale?: string
    date_format?: string
    time_format?: string
    number_format?: string
    percent_places?: number
    currency?: string
    currency_display?: string
    ui_state?: UiState
    user_name_display?: string
    full_name_order?: string
    searxng_url?: string
    web_search?: boolean
    web_search_engine?: string
    select_on_focus?: boolean
    word_dictionary?: boolean
    trim_spaces?: boolean
    journal_days?: number
    show_data_journal?: boolean
    show_system_journal?: boolean
    journal_layout?: string
    auto_scope?: boolean
    scope_threshold?: string
  }) {
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
    if (isDateFormat(p.date_format)) {
      dateFormat.value = p.date_format
      store(DATE_FORMAT_STORAGE_KEY, p.date_format)
    }
    if (isTimeFormat(p.time_format)) {
      timeFormat.value = p.time_format
      store(TIME_FORMAT_STORAGE_KEY, p.time_format)
    }
    if (isNumberFormat(p.number_format)) {
      numberFormat.value = p.number_format
      numberSettings.format = p.number_format
      store(NUMBER_FORMAT_STORAGE_KEY, p.number_format)
    }
    if (isPercentPlaces(p.percent_places)) {
      percentPlaces.value = p.percent_places
      numberSettings.percentPlaces = p.percent_places
      store(PERCENT_PLACES_STORAGE_KEY, String(p.percent_places))
    }
    if (isCurrency(p.currency)) {
      currency.value = p.currency
      store(CURRENCY_STORAGE_KEY, p.currency)
    }
    if (isCurrencyDisplay(p.currency_display)) {
      currencyDisplay.value = p.currency_display
      numberSettings.currency = p.currency_display
      store(CURRENCY_DISPLAY_STORAGE_KEY, p.currency_display)
    }
    if (p.ui_state && typeof p.ui_state === 'object') uiState.value = p.ui_state
    if ((USER_NAME_DISPLAYS as readonly unknown[]).includes(p.user_name_display)) {
      userNameDisplay.value = p.user_name_display as UserNameDisplay
    }
    if ((FULL_NAME_ORDERS as readonly unknown[]).includes(p.full_name_order)) {
      fullNameOrder.value = p.full_name_order as FullNameOrder
    }
    if (typeof p.searxng_url === 'string') searxngUrl.value = p.searxng_url
    if (typeof p.web_search === 'boolean') {
      webSearch.value = p.web_search
      store(WEB_SEARCH_ON_STORAGE_KEY, String(p.web_search))
    }
    if (isWebSearchEngine(p.web_search_engine)) {
      webSearchEngine.value = p.web_search_engine
      store(WEB_SEARCH_STORAGE_KEY, p.web_search_engine)
    }
    if (typeof p.select_on_focus === 'boolean') {
      selectOnFocus.value = p.select_on_focus
      store(SELECT_ON_FOCUS_STORAGE_KEY, String(p.select_on_focus))
    }
    if (typeof p.word_dictionary === 'boolean') wordDictionary.value = p.word_dictionary
    if (typeof p.trim_spaces === 'boolean') trimSpaces.value = p.trim_spaces
    if (isJournalDays(p.journal_days)) journalDays.value = p.journal_days
    if (typeof p.show_data_journal === 'boolean') showDataJournal.value = p.show_data_journal
    if (typeof p.show_system_journal === 'boolean') showSystemJournal.value = p.show_system_journal
    if (isJournalLayout(p.journal_layout)) journalLayout.value = p.journal_layout
    if (typeof p.auto_scope === 'boolean') {
      autoScope.value = p.auto_scope
      store(AUTO_SCOPE_STORAGE_KEY, String(p.auto_scope))
    }
    if (typeof p.scope_threshold === 'string' && p.scope_threshold) {
      scopeThreshold.value = p.scope_threshold
      store(SCOPE_THRESHOLD_STORAGE_KEY, p.scope_threshold)
    }
  }

  /** Try a search on a SearXNG address (not saved); resolves with how many images came. */
  function testSearxng(url: string) {
    return api<{ results: number }>('/auth/preferences/test-searxng/', {
      method: 'POST',
      body: JSON.stringify({ searxng_url: url }),
    })
  }

  /** Apply immediately and save to the account; if the API fails, roll back and rethrow. */
  async function save(changes: PreferencesUpdate) {
    const previous = {
      language: language.value,
      theme: theme.value,
      color_theme: colorTheme.value,
      ui_scale: uiScale.value,
      date_format: dateFormat.value,
      time_format: timeFormat.value,
      number_format: numberFormat.value,
      percent_places: percentPlaces.value,
      currency: currency.value,
      currency_display: currencyDisplay.value,
      ui_state: uiState.value,
      user_name_display: userNameDisplay.value,
      full_name_order: fullNameOrder.value,
      searxng_url: searxngUrl.value,
      web_search: webSearch.value,
      web_search_engine: webSearchEngine.value,
      select_on_focus: selectOnFocus.value,
      word_dictionary: wordDictionary.value,
      trim_spaces: trimSpaces.value,
      journal_days: journalDays.value,
      show_data_journal: showDataJournal.value,
      show_system_journal: showSystemJournal.value,
      journal_layout: journalLayout.value,
      auto_scope: autoScope.value,
      scope_threshold: scopeThreshold.value,
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

  /**
   * Change part of the interface's state and save it to the account (quietly: a failure only
   * loses it on other computers; this one keeps it).
   */
  function saveUiState(change: (state: UiState) => UiState) {
    const next = change(structuredClone(toRaw(uiState.value)))
    uiState.value = next
    api('/auth/preferences/', { method: 'PATCH', body: JSON.stringify({ ui_state: next }) }).catch(
      () => {},
    )
  }

  return {
    language,
    theme,
    colorTheme,
    uiScale,
    dateFormat,
    timeFormat,
    numberFormat,
    percentPlaces,
    currency,
    currencyDisplay,
    uiState,
    saveUiState,
    userNameDisplay,
    fullNameOrder,
    searxngUrl,
    webSearch,
    webSearchEngine,
    selectOnFocus,
    wordDictionary,
    trimSpaces,
    journalDays,
    showDataJournal,
    showSystemJournal,
    journalLayout,
    autoScope,
    scopeThreshold,
    apply,
    save,
    testSearxng,
  }
})
