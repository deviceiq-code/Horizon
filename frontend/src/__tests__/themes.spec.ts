import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it } from 'vitest'

import { usePreferencesStore } from '@/stores/preferences'
import { COLOR_THEMES, DEFAULT_COLOR_THEME, vuetifyThemeName, vuetifyThemes } from '@/themes'

describe('color themes', () => {
  it('Emerald Slate is the default and comes first; every theme in a light and a dark version', () => {
    expect(DEFAULT_COLOR_THEME).toBe('emerald_slate')
    expect(COLOR_THEMES[0]!.id).toBe('emerald_slate')
    expect(Object.keys(vuetifyThemes())).toEqual([
      'emerald_slate-light',
      'emerald_slate-dark',
      'metallic_foundations-light',
      'metallic_foundations-dark',
      'earthy_serene-light',
      'earthy_serene-dark',
      'sleek_futuristic-light',
      'sleek_futuristic-dark',
    ])
  })

  it('Metallic Foundations is available too', () => {
    const theme = COLOR_THEMES.find((t) => t.id === 'metallic_foundations')!
    expect(theme.name).toBe('Metallic Foundations')
    expect(theme.swatches).toEqual(['#3D52A0', '#7091E6', '#8697C4', '#ADBBDA', '#EDE8F5'])
    expect(theme.light.colors!.primary).toBe('#3D52A0')
    expect(theme.light.colors!.background).toBe('#EDE8F5')
    expect(theme.dark.dark).toBe(true)
    expect(theme.fontName).toBe('Ubuntu')
    expect(theme.fontFamily.startsWith("'Ubuntu'")).toBe(true)
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

  it('Emerald Slate: emerald green over slate, Public Sans', () => {
    const theme = COLOR_THEMES.find((t) => t.id === 'emerald_slate')!
    expect(theme.name).toBe('Emerald Slate')
    expect(theme.fontName).toBe('Public Sans')
    expect(theme.light.colors!.primary).toBe('#00926F')
    expect(theme.light.colors!.sidebar).toBe('#1C252E')
    expect(theme.dark.colors!.background).toBe('#141A21')
  })

  it('every theme colors the side menu and gets the card shadow', () => {
    for (const [name, definition] of Object.entries(vuetifyThemes())) {
      expect({ name, sidebar: definition.colors!.sidebar }).toEqual({
        name,
        sidebar: expect.any(String),
      })
      expect(definition.colors!['sidebar-active']).toMatch(/^#/)
      expect(definition.variables!['card-shadow']).toContain('rgba')
    }
  })

  it('names the Vuetify theme from the color theme and the mode', () => {
    expect(vuetifyThemeName('metallic_foundations', false)).toBe('metallic_foundations-light')
    expect(vuetifyThemeName('metallic_foundations', true)).toBe('metallic_foundations-dark')
    // An unknown theme (e.g. removed later) falls back to the default
    expect(vuetifyThemeName('neon', true)).toBe('emerald_slate-dark')
  })
})

describe('preferences: color theme', () => {
  beforeEach(() => {
    localStorage.clear()
    setActivePinia(createPinia())
  })

  it('applies known color themes, remembers them in the browser and ignores unknown ones', () => {
    const preferences = usePreferencesStore()
    expect(preferences.colorTheme).toBe('emerald_slate')
    preferences.apply({ color_theme: 'neon' })
    expect(preferences.colorTheme).toBe('emerald_slate')
    preferences.apply({ color_theme: 'metallic_foundations' })
    expect(localStorage.getItem('horizon.colorTheme')).toBe('metallic_foundations')
  })
})
