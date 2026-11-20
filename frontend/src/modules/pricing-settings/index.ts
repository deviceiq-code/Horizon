import type { AppModule } from '@/modules'

/** Pricing control panel (limits used by the analyses): administrators only. */
const pricingSettings: AppModule = {
  name: 'pricing-settings',
  icon: 'mdi-tune-variant',
  titleKey: 'pricingSettings.title',
  app: 'pricing',
  adminOnly: true,
  routes: [
    {
      path: 'control-panel',
      name: 'pricing-settings',
      component: () => import('./PricingSettingsView.vue'),
    },
  ],
}

export default pricingSettings
