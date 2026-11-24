/**
 * The apps of the Horizon suite (like Microsoft 365's): each one groups modules (src/modules)
 * under its own address prefix and side menu. "Administration" holds what every app shares:
 * users and roles; catalogs (customers, service providers, verticals…).
 */
export type AppId = 'pricing' | 'remarketing' | 'partners' | 'admin'

export interface SuiteApp {
  id: AppId
  /** Address prefix of the app's pages ("/pricing/...") */
  path: string
  /** App name (not translated, e.g. "Pricing"); absent when translated with titleKey */
  name?: string
  /** Translated name (areas like Administration) */
  titleKey?: string
  descriptionKey: string
  icon: string
  /** Not available yet: shown as "coming soon" */
  comingSoon?: boolean
}

export const SUITE_APPS: readonly SuiteApp[] = [
  {
    id: 'pricing',
    path: 'pricing',
    name: 'Pricing',
    descriptionKey: 'apps.pricing.description',
    // Not used by any module (Average Prices has mdi-chart-timeline-variant)
    icon: 'mdi-sale-outline',
  },
  {
    id: 'remarketing',
    path: 'remarketing',
    name: 'Remarketing',
    descriptionKey: 'apps.remarketing.description',
    icon: 'mdi-storefront-outline',
  },
  {
    id: 'partners',
    path: 'partners',
    name: 'Services and Partnerships',
    descriptionKey: 'apps.partners.description',
    icon: 'mdi-handshake-outline',
  },
  {
    id: 'admin',
    path: 'admin',
    titleKey: 'apps.admin.title',
    descriptionKey: 'apps.admin.description',
    icon: 'mdi-shield-crown-outline',
  },
]

export function suiteApp(id: string | undefined | null): SuiteApp | undefined {
  return SUITE_APPS.find((app) => app.id === id)
}

type Translate = (key: string) => string

/** "Pricing" / "Administração". */
export function appName(app: SuiteApp, t: Translate): string {
  return app.name ?? t(app.titleKey!)
}
