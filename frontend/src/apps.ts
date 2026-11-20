/**
 * The apps of the Horizon suite (like Microsoft 365's): each one groups modules (src/modules)
 * under its own address prefix and side menu. "Administration" holds what every app shares:
 * catalogs, customers, account managers, users and system settings.
 */
export type AppId = 'pricing' | 'remarketing' | 'admin'

export interface SuiteApp {
  id: AppId
  /** Address prefix of the app's pages ("/pricing/...") */
  path: string
  /** Brand name (not translated); absent when the name is translated with titleKey */
  name?: string
  /** Short brand name for the breadcrumb ("Pricing") */
  shortName?: string
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
    name: 'Horizon Pricing',
    shortName: 'Pricing',
    descriptionKey: 'apps.pricing.description',
    icon: 'mdi-chart-timeline-variant',
  },
  {
    id: 'remarketing',
    path: 'remarketing',
    name: 'Horizon Remarketing',
    shortName: 'Remarketing',
    descriptionKey: 'apps.remarketing.description',
    icon: 'mdi-storefront-outline',
    comingSoon: true,
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

/** Full name: "Horizon Pricing" / "Administração". */
export function appName(app: SuiteApp, t: Translate): string {
  return app.name ?? t(app.titleKey!)
}

/** Name in the breadcrumb: "Pricing" / "Administração". */
export function appShortName(app: SuiteApp, t: Translate): string {
  return app.shortName ?? appName(app, t)
}
