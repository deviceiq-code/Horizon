import type { Messages } from './en'

const es: Messages = {
  app: {
    name: 'Sistema Horizon',
    description: 'Valoración de residuales de leasing operativo',
  },
  common: {
    logout: 'Salir',
  },
  language: {
    select: 'Seleccionar idioma',
  },
  login: {
    username: 'Usuario',
    password: 'Contraseña',
    submit: 'Entrar',
    invalidCredentials: 'Usuario o contraseña inválidos.',
  },
  menu: {
    open: 'Abrir menú',
    home: 'Inicio',
    settings: 'Configuración',
  },
  home: {
    welcome: 'Bienvenido, {name}',
    text: 'El entorno está funcionando. Aquí estarán las pantallas de activos, curvas de residual y simulaciones de valoración.',
  },
  settings: {
    title: 'Configuración',
    subtitle: 'Sus preferencias se guardan en su cuenta y valen en cualquier dispositivo.',
    language: 'Idioma',
    languageDescription: 'Idioma de la interfaz y de los mensajes del sistema.',
    appearance: 'Apariencia',
    theme: 'Tema',
    themeDescription: 'Colores claros, oscuros o iguales a los de su sistema operativo.',
    themes: {
      light: 'Claro',
      dark: 'Oscuro',
      system: 'Sistema',
    },
    saved: 'Preferencias guardadas.',
    saveError: 'No se pudieron guardar las preferencias. Inténtelo de nuevo.',
  },
}

export default es
