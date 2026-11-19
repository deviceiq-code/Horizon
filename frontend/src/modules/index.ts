/**
 * Registry of the system's modules. Each module gets an icon in the side menu and its
 * routes are mounted under MainLayout. To add a module, create src/modules/<name>/index.ts
 * exporting an AppModule and list it in MODULES (menu order).
 */
import type { RouteRecordRaw } from 'vue-router'

import accountManagers from './account-managers'
import catalogs from './catalogs'
import customers from './customers'

export interface AppModule {
  /** Route name of the module's main page (the menu links to it) */
  name: string
  /** MDI icon shown in the side menu */
  icon: string
  /** Translation key of the module title (menu label and page title) */
  titleKey: string
  /** Routes relative to "/" (children of MainLayout) */
  routes: RouteRecordRaw[]
  /** 'main' (default): business modules at the top of the menu; 'system': bottom group */
  placement?: 'main' | 'system'
}

export const MODULES: AppModule[] = [customers, accountManagers, catalogs]
