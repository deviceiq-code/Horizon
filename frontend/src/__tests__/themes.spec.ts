import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it } from 'vitest'

import { usePreferencesStore } from '@/stores/preferences'
import { COLOR_THEMES, DEFAULT_COLOR_THEME, vuetifyThemeName, vuetifyThemes } from '@/themes'

describe('color themes', () => {
  it('Metallic Foundations is the default, in a light and a dark version', () => {
    expect(DEFAULT_COLOR_THEME).toBe('metallic_foundations')
    const theme = COLOR_THEMES.find((t) => t.id === DEFAULT_COLOR_THEME)!
    expect(theme.name).toBe('Metallic Foundations')
    expect(theme.swatches).toEqual(['#3D52A0', '#7091E6', '#8697C4', '#ADBBDA', '#EDE8F5'])
    expect(theme.light.colors!.primary).toBe('#3D52A0')
    expect(theme.light.colors!.background).toBe('#EDE8F5')
    expect(theme.dark.dark).toBe(true)
    expect(theme.fontName).toBe('Ubuntu')
    expect(theme.fontFamily.startsWith("'Ubuntu'")).toBe(true)
    expect(Object.keys(vuetifyThemes())).toEqual([
      'metallic_foundations-light',
      'metallic_foundations-dark',
      'earthy_serene-light',
      'earthy_serene-dark',
      'sleek_futuristic-light',
      'sleek_futuristic-dark',
    ])
  })

  it('Earthy and Serene is available too', () => {
    const theme = COLOR_THEMES.find((t) => t.id === 'earthy_serene')!
    expect(theme.name).toBe('Earthy and Serene')
    expect(theme.swatches).toEqual(['#3E362E', '#865D36', '#93785B', '#AC8968', '#A69080'])
    expect(theme.light.colors!.primary).toBe('#865D36')
    expect(vuetifyThemeName('earthy_serene', true)).toBe('earthy_serene-dark')
  })

  it('Sleek and Futuristic is available too', () => {
    const theme = COLOR_THEMES.find((t) => t.id === 'sleek_futuristic')!
    expect(theme.name).toBe('Sleek and Futuristic')
    expect(theme.swatches).toEqual(['#2C3531', '#116466', '#D9B08C', '#FFCB9A', '#D1E8E2'])
    expect(theme.light.colors!.primary).toBe('#116466')
    expect(vuetifyThemeName('sleek_futuristic', false)).toBe('sleek_futuristic-light')
  })

  it('names the Vuetify theme from the color theme and the mode', () => {
    expect(vuetifyThemeName('metallic_foundations', false)).toBe('metallic_foundations-light')
    expect(vuetifyThemeName('metallic_foundations', true)).toBe('metallic_foundations-dark')
    // An unknown theme (e.g. removed later) falls back to the default
    expect(vuetifyThemeName('neon', true)).toBe('metallic_foundations-dark')
  })
})

describe('preferences: color theme', () => {
  beforeEach(() => {
    localStorage.clear()
    setActivePinia(createPinia())
  })

  it('applies known color themes, remembers them in the browser and ignores unknown ones', () => {
    const preferences = usePreferencesStore()
    expect(preferences.colorTheme).toBe('metallic_foundations')
    preferences.apply({ color_theme: 'neon' })
    expect(preferences.colorTheme).toBe('metallic_foundations')
    preferences.apply({ color_theme: 'metallic_foundations' })
    expect(localStorage.getItem('horizon.colorTheme')).toBe('metallic_foundations')
  })
})
