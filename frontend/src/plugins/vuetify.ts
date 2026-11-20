import 'vuetify/styles'
import '@mdi/font/css/materialdesignicons.css'
import { createVuetify } from 'vuetify'
import { createVueI18nAdapter } from 'vuetify/locale/adapters/vue-i18n'
import { useI18n } from 'vue-i18n'

import { i18n } from '@/i18n'
import { DEFAULT_COLOR_THEME, vuetifyThemeName, vuetifyThemes } from '@/themes'

export default createVuetify({
  // Vuetify's built-in strings (pagination, "no data", etc.) follow the vue-i18n language
  locale: {
    adapter: createVueI18nAdapter({ i18n, useI18n }),
  },
  theme: {
    // Color themes (src/themes.ts), each in a light and a dark version. The one in use is
    // applied in App.vue from the user's preferences.
    defaultTheme: vuetifyThemeName(DEFAULT_COLOR_THEME, false),
    themes: vuetifyThemes(),
  },
  // Same look for every form field
  defaults: {
    VTextField: { variant: 'outlined', density: 'comfortable' },
    VSelect: { variant: 'outlined', density: 'comfortable' },
    VAutocomplete: { variant: 'outlined', density: 'comfortable' },
    VCombobox: { variant: 'outlined', density: 'comfortable' },
    VTextarea: { variant: 'outlined', density: 'comfortable' },
  },
})
