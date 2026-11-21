/**
 * Themes of the interface: colors and font. Besides Vuetify's colors, each version has the side
 * menu's: sidebar (background), on-sidebar (text), on-sidebar-strong (hovered/open page) and
 * sidebar-active (the open page's mark). Each one has a light and a dark version (Vuetify themes named
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
      // Side menu: deep navy, soft blue text, the light blue marks the open page
      sidebar: '#1F2747',
      'on-sidebar': '#ADBBDA',
      'on-sidebar-strong': '#FFFFFF',
      'sidebar-active': '#7091E6',
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
      sidebar: '#1C2445',
      'on-sidebar': '#ADBBDA',
      'on-sidebar-strong': '#FFFFFF',
      'sidebar-active': '#7091E6',
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
      sidebar: '#3E362E',
      'on-sidebar': '#C9B8A6',
      'on-sidebar-strong': '#FFFFFF',
      'sidebar-active': '#C9A57F',
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
      sidebar: '#2F2924',
      'on-sidebar': '#C9B8A6',
      'on-sidebar-strong': '#FFFFFF',
      'sidebar-active': '#C9A57F',
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
      sidebar: '#2C3531',
      'on-sidebar': '#A9C7BF',
      'on-sidebar-strong': '#FFFFFF',
      'sidebar-active': '#4FB3B0',
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
      sidebar: '#2C3531',
      'on-sidebar': '#A9C7BF',
      'on-sidebar-strong': '#FFFFFF',
      'sidebar-active': '#4FB3B0',
    },
  },
}

/**
 * "Emerald Slate": emerald green over slate grays — a clean dashboard look (dark slate side
 * menu, near-white page, white cards). Font: Public Sans.
 */
const emeraldSlate: ColorTheme = {
  id: 'emerald_slate',
  name: 'Emerald Slate',
  swatches: ['#1C252E', '#00926F', '#00A883', '#CBEEE0', '#F9FAFB'],
  fontFamily: "'Public Sans', 'Segoe UI', Roboto, sans-serif",
  fontName: 'Public Sans',
  light: {
    dark: false,
    colors: {
      primary: '#00926F',
      secondary: '#00A883',
      accent: '#CBEEE0',
      info: '#1C69E3',
      success: '#009957',
      warning: '#E16600',
      error: '#E40014',
      background: '#F9FAFB',
      surface: '#FFFFFF',
      'surface-bright': '#FFFFFF',
      'surface-light': '#F4F6F8',
      'surface-variant': '#1C252E',
      'on-surface-variant': '#FFFFFF',
      'on-background': '#1C252E',
      'on-surface': '#1C252E',
      sidebar: '#1C252E',
      'on-sidebar': '#919EAB',
      'on-sidebar-strong': '#FFFFFF',
      'sidebar-active': '#00A76F',
    },
    variables: {
      'border-color': '#919EAB',
      'border-opacity': 0.24,
      'medium-emphasis-opacity': 0.68,
    },
  },
  dark: {
    dark: true,
    colors: {
      primary: '#00AB81',
      secondary: '#00C296',
      accent: '#00765A',
      info: '#5B9BFF',
      success: '#22C55E',
      warning: '#FF9A3C',
      error: '#FF5A5F',
      background: '#141A21',
      surface: '#1C252E',
      'surface-bright': '#252F3A',
      'surface-light': '#252F3A',
      'surface-variant': '#919EAB',
      'on-surface-variant': '#141A21',
      'on-background': '#FFFFFF',
      'on-surface': '#FFFFFF',
      sidebar: '#1C252E',
      'on-sidebar': '#919EAB',
      'on-sidebar-strong': '#FFFFFF',
      'sidebar-active': '#00C296',
    },
    variables: {
      'border-color': '#919EAB',
      'border-opacity': 0.16,
      'medium-emphasis-opacity': 0.72,
    },
  },
}

export const COLOR_THEMES: readonly ColorTheme[] = [
  metallicFoundations,
  earthySerene,
  sleekFuturistic,
  emeraldSlate,
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

/** Soft card shadows (main.css: --v-card-shadow), lighter over dark backgrounds. */
const CARD_SHADOW = {
  light: '0 0 2px 0 rgba(145, 158, 171, 0.2), 0 12px 24px -4px rgba(145, 158, 171, 0.12)',
  dark: '0 0 2px 0 rgba(0, 0, 0, 0.2), 0 12px 24px -4px rgba(0, 0, 0, 0.12)',
}

function withShared(definition: ThemeDefinition, dark: boolean): ThemeDefinition {
  return {
    ...definition,
    variables: {
      'card-shadow': CARD_SHADOW[dark ? 'dark' : 'light'],
      ...definition.variables,
    },
  }
}

/** Every version of every theme, for createVuetify. */
export function vuetifyThemes(): Record<string, ThemeDefinition> {
  return Object.fromEntries(
    COLOR_THEMES.flatMap((theme) => [
      [`${theme.id}-light`, withShared(theme.light, false)],
      [`${theme.id}-dark`, withShared(theme.dark, true)],
    ]),
  )
}

/** The theme with this id (the default one when unknown). */
export function colorThemeById(id: string): ColorTheme {
  return COLOR_THEMES.find((theme) => theme.id === id) ?? COLOR_THEMES[0]!
}
