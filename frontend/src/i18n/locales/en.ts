/**
 * UI strings in English — the reference language.
 * Other languages are typed with `Messages` and must have exactly the same keys.
 * Note: in vue-i18n the characters { } @ $ | have special meaning.
 */
const en = {
  app: {
    name: 'Horizon System',
    description: 'Operating lease residual value pricing',
  },
  common: {
    logout: 'Sign out',
  },
  language: {
    select: 'Select language',
  },
  login: {
    username: 'Username',
    password: 'Password',
    submit: 'Sign in',
    invalidCredentials: 'Invalid username or password.',
  },
  menu: {
    open: 'Open menu',
    home: 'Home',
    settings: 'Settings',
  },
  home: {
    welcome: 'Welcome, {name}',
    text: 'The environment is up and running. Asset, residual curve and pricing simulation screens will live here.',
  },
  settings: {
    title: 'Settings',
    subtitle: 'Your preferences are saved to your account and apply on any device.',
    language: 'Language',
    languageDescription: 'Language used by the interface and system messages.',
    appearance: 'Appearance',
    theme: 'Theme',
    themeDescription: 'Light colors, dark colors, or match your operating system.',
    themes: {
      light: 'Light',
      dark: 'Dark',
      system: 'System',
    },
    saved: 'Preferences saved.',
    saveError: 'Could not save your preferences. Please try again.',
  },
}

export type Messages = typeof en
export default en
