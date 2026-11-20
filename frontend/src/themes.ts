/**
 * Themes of the interface: colors and font. Each one has a light and a dark version (Vuetify themes named
 * "<id>-light" / "<id>-dark"); the user's mode (light, dark or system) picks the version.
 * To add a theme: a new entry here and its id in the backend's accounts.models.ColorTheme.
 */
import type { ThemeDefinition } from 'vuetify'

export interface ColorTheme {
  /** Stored in the user's preferences (backend ColorTheme) */
  id: string
  /** Proper name, shown as is in every language */
  name: string
  /** Colors shown as a sample in Settings */
  swatches: string[]
  /** CSS font-family of the whole interface (the font files are loaded in main.ts) */
  fontFamily: string
  /** The font's name, shown in Settings */
  fontName: string
  light: ThemeDefinition
  dark: ThemeDefinition
}

/** "Metallic Foundations": deep and soft blues over a pale lavender. */
const metallicFoundations: ColorTheme = {
  id: 'metallic_foundations',
  name: 'Metallic Foundations',
  swatches: ['#3D52A0', '#7091E6', '#8697C4', '#ADBBDA', '#EDE8F5'],
  fontFamily: "'Ubuntu', 'Segoe UI', Roboto, sans-serif",
  fontName: 'Ubuntu',
  light: {
    dark: false,
    colors: {
      primary: '#3D52A0',
      secondary: '#7091E6',
      accent: '#8697C4',
      info: '#7091E6',
      background: '#EDE8F5',
      surface: '#FFFFFF',
      'surface-bright': '#FFFFFF',
      'surface-light': '#F3F0FA',
      'surface-variant': '#ADBBDA',
      'on-surface-variant': '#1F2747',
      'on-background': '#1F2747',
      'on-surface': '#1F2747',
      // Top bar: a metallic sheen from the deep to the soft blue
      'app-bar': '#3D52A0',
      'app-bar-end': '#7091E6',
    },
  },
  dark: {
    dark: true,
    colors: {
      primary: '#7091E6',
      secondary: '#ADBBDA',
      accent: '#8697C4',
      info: '#8697C4',
      background: '#131931',
      surface: '#1C2445',
      'surface-bright': '#2A3563',
      'surface-light': '#242D55',
      'surface-variant': '#3D52A0',
      'on-surface-variant': '#EDE8F5',
      'on-background': '#EDE8F5',
      'on-surface': '#EDE8F5',
      'app-bar': '#1C2445',
      'app-bar-end': '#3D52A0',
    },
  },
}

/** "Earthy and Serene": espresso, walnut and warm sand tones. */
const earthySerene: ColorTheme = {
  id: 'earthy_serene',
  name: 'Earthy and Serene',
  swatches: ['#3E362E', '#865D36', '#93785B', '#AC8968', '#A69080'],
  fontFamily: "'Ubuntu', 'Segoe UI', Roboto, sans-serif",
  fontName: 'Ubuntu',
  light: {
    dark: false,
    colors: {
      primary: '#865D36',
      secondary: '#93785B',
      accent: '#AC8968',
      info: '#93785B',
      // The palette has no pale tone: a warm cream derived from #A69080
      background: '#F3EEE8',
      surface: '#FFFFFF',
      'surface-bright': '#FFFFFF',
      'surface-light': '#F7F2EC',
      'surface-variant': '#A69080',
      'on-surface-variant': '#3E362E',
      'on-background': '#3E362E',
      'on-surface': '#3E362E',
      'app-bar': '#3E362E',
      'app-bar-end': '#865D36',
    },
  },
  dark: {
    dark: true,
    colors: {
      // A lighter tan than #AC8968, readable over the dark espresso
      primary: '#C9A57F',
      secondary: '#A69080',
      accent: '#AC8968',
      info: '#A69080',
      background: '#221D18',
      surface: '#2F2924',
      'surface-bright': '#4A4037',
      'surface-light': '#3E362E',
      'surface-variant': '#865D36',
      'on-surface-variant': '#F1E9E1',
      'on-background': '#F1E9E1',
      'on-surface': '#F1E9E1',
      'app-bar': '#2A241F',
      'app-bar-end': '#865D36',
    },
  },
}

/** "Sleek and Futuristic": deep teal over graphite, with warm peach highlights. */
const sleekFuturistic: ColorTheme = {
  id: 'sleek_futuristic',
  name: 'Sleek and Futuristic',
  swatches: ['#2C3531', '#116466', '#D9B08C', '#FFCB9A', '#D1E8E2'],
  fontFamily: "'Ubuntu', 'Segoe UI', Roboto, sans-serif",
  fontName: 'Ubuntu',
  light: {
    dark: false,
    colors: {
      primary: '#116466',
      secondary: '#D9B08C',
      accent: '#FFCB9A',
      info: '#116466',
      background: '#D1E8E2',
      surface: '#FFFFFF',
      'surface-bright': '#FFFFFF',
      'surface-light': '#EEF6F3',
      'surface-variant': '#D9B08C',
      'on-surface-variant': '#2C3531',
      'on-background': '#2C3531',
      'on-surface': '#2C3531',
      'app-bar': '#2C3531',
      'app-bar-end': '#116466',
    },
  },
  dark: {
    dark: true,
    colors: {
      // A lighter teal than #116466, readable over the graphite
      primary: '#4FB3B0',
      secondary: '#FFCB9A',
      accent: '#D9B08C',
      info: '#4FB3B0',
      background: '#1C2321',
      surface: '#2C3531',
      'surface-bright': '#3E4A45',
      'surface-light': '#34403B',
      'surface-variant': '#116466',
      'on-surface-variant': '#D1E8E2',
      'on-background': '#D1E8E2',
      'on-surface': '#E6F2EE',
      'app-bar': '#1C2321',
      'app-bar-end': '#116466',
    },
  },
}

export const COLOR_THEMES: readonly ColorTheme[] = [
  metallicFoundations,
  earthySerene,
  sleekFuturistic,
]

export const DEFAULT_COLOR_THEME = metallicFoundations.id

export function isColorTheme(id: string | null | undefined): boolean {
  return COLOR_THEMES.some((theme) => theme.id === id)
}

/** Vuetify theme name for a color theme and a resolved mode. */
export function vuetifyThemeName(colorTheme: string, dark: boolean): string {
  const id = isColorTheme(colorTheme) ? colorTheme : DEFAULT_COLOR_THEME
  return `${id}-${dark ? 'dark' : 'light'}`
}

/** Every version of every theme, for createVuetify. */
export function vuetifyThemes(): Record<string, ThemeDefinition> {
  return Object.fromEntries(
    COLOR_THEMES.flatMap((theme) => [
      [`${theme.id}-light`, theme.light],
      [`${theme.id}-dark`, theme.dark],
    ]),
  )
}

/** The theme with this id (the default one when unknown). */
export function colorThemeById(id: string): ColorTheme {
  return COLOR_THEMES.find((theme) => theme.id === id) ?? COLOR_THEMES[0]!
}
