/**
 * Registry of the suite's modules. Each module belongs to an app (src/apps.ts): its routes are
 * mounted under MainLayout with the app's prefix ("/pricing/average-prices") and it gets an
 * icon in that app's side menu. To add a module, create src/modules/<name>/index.ts exporting
 * an AppModule and list it in MODULES (menu order).
 */
import type { RouteRecordRaw } from 'vue-router'
import { suiteApp, type AppId } from '@/apps'

import averagePrices from './average-prices'
import catalogs from './catalogs'
import customers from './customers'
import efmvAnalyses from './efmv-analyses'
import inventory from './inventory'
import partners from './partners'
import pricingSettings from './pricing-settings'
import serviceProviders from './service-providers'
import { roles, users } from './users'
import warehouses from './warehouses'

export interface AppModule {
  /** Route name of the module's main page (the menu links to it) */
  name: string
  /** MDI icon shown in the side menu */
  icon: string
  /** Translation key of the module title (menu label and page title) */
  titleKey: string
  /** The app it belongs to (its routes get the app's address prefix) */
  app: AppId
  /** Routes relative to the app ("average-prices" → "/pricing/average-prices") */
  routes: RouteRecordRaw[]
  /** Only administrators see it in the menu and can open its routes */
  adminOnly?: boolean
  /**
   * Translation key of its section in the side menu ("menu.sections.management"); without
   * one, the section is named after the app
   */
  section?: string
}

/** Modules the user can open (admin-only ones need an administrator). */
export function visibleModules(isAdmin: boolean): AppModule[] {
  return MODULES.filter((module) => isAdmin || !module.adminOnly)
}

export const MODULES: AppModule[] = [
  // Pricing: eFMV Analyses first
  efmvAnalyses,
  averagePrices,
  pricingSettings,
  // Remarketing: Inventory
  ...inventory,
  warehouses,
  // Services and Partnerships (a skeleton for now)
  ...partners,
  // Administration: Management, then Catalogs (customers and service providers first)
  users,
  roles,
  customers,
  serviceProviders,
  ...catalogs,
]

/** Modules of an app the user can open, in menu order. */
export function appModules(app: AppId | undefined, isAdmin: boolean): AppModule[] {
  return visibleModules(isAdmin).filter((module) => module.app === app)
}

/**
 * Routes of every module under its app's prefix, with what the layout needs in `meta`: the
 * app, the module and its title (breadcrumb) and whether administrators only can open it.
 * The former addresses without the prefix redirect to the new ones.
 */
export function moduleRoutes(): RouteRecordRaw[] {
  return MODULES.flatMap((module) => {
    const prefix = suiteApp(module.app)!.path
    return module.routes.flatMap((route) => [
      {
        ...route,
        path: `${prefix}/${route.path}`,
        meta: {
          ...route.meta,
          app: module.app,
          module: module.name,
          titleKey: module.titleKey,
          adminOnly: !!module.adminOnly,
        },
      } as RouteRecordRaw,
      {
        path: `/${route.path}/:rest(.*)*`,
        redirect: (to) => `/${prefix}${to.fullPath}`,
      } as RouteRecordRaw,
    ])
  })
}
