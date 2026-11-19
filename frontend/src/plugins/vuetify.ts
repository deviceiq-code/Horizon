import 'vuetify/styles'
import '@mdi/font/css/materialdesignicons.css'
import { createVuetify } from 'vuetify'
import { pt } from 'vuetify/locale'

export default createVuetify({
  locale: {
    locale: 'pt',
    fallback: 'pt',
    messages: { pt },
  },
  theme: {
    defaultTheme: 'horizon',
    themes: {
      horizon: {
        dark: false,
        colors: {
          primary: '#1E4E8C',
          secondary: '#5C6B7A',
          background: '#F5F7FA',
        },
      },
    },
  },
  defaults: {
    VTextField: { variant: 'outlined', density: 'comfortable' },
    VSelect: { variant: 'outlined', density: 'comfortable' },
  },
})
