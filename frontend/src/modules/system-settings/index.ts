import type { AppModule } from '@/modules'

/** Settings for every user (how users are shown, photo search…): administrators only. */
const systemSettings: AppModule = {
  name: 'system-settings',
  icon: 'mdi-cog-outline',
  titleKey: 'settings.tabs.system',
  app: 'admin',
  adminOnly: true,
  routes: [
    {
      path: 'system-settings',
      name: 'system-settings',
      component: () => import('./SystemSettingsView.vue'),
    },
  ],
}

export default systemSettings
