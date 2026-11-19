import 'vuetify/styles'
import '@mdi/font/css/materialdesignicons.css'
import { createVuetify } from 'vuetify'
import { createVueI18nAdapter } from 'vuetify/locale/adapters/vue-i18n'
import { useI18n } from 'vue-i18n'

import { i18n } from '@/i18n'

export default createVuetify({
  // Vuetify's built-in strings (pagination, "no data", etc.) follow the vue-i18n language
  locale: {
    adapter: createVueI18nAdapter({ i18n, useI18n }),
  },
  theme: {
    // 'system' switches between the 'light' and 'dark' themes based on the operating system.
    // The effective theme is applied in App.vue from the user's preferences.
    defaultTheme: 'system',
    themes: {
      light: {
        dark: false,
        colors: {
          primary: '#1E4E8C',
          secondary: '#5C6B7A',
          background: '#F5F7FA',
        },
      },
      dark: {
        dark: true,
        colors: {
          primary: '#7BA7E0',
          secondary: '#9AA8B6',
          background: '#121417',
          surface: '#1C1F24',
        },
      },
    },
  },
  defaults: {
    VTextField: { variant: 'outlined', density: 'comfortable' },
    VSelect: { variant: 'outlined', density: 'comfortable' },
  },
})
