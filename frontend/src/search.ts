/**
 * Centralized search (backend search/registry.py): one search over every module, each category
 * shown and opened the same way. A category is a module: its icon and title come from MODULES,
 * a result opens the module's grid already searching for it (`?search=`, ServerCrudTable) or
 * its own page. Pages (the modules and the user's pages) are searched here, by their names in
 * the UI language.
 */

import type { RouteLocationRaw } from 'vue-router'
import { api, queryString } from '@/api'
import { appName, suiteApp } from '@/apps'
import { visibleModules } from '@/modules'

export interface SearchResult {
  id: number
  title: string
  subtitle: string
  meta: string
  badge: { text: string; color: string } | null
  /** What to type in the module's grid to find it */
  search: string
  amount: { value: string; currency: string } | null
  /** People: their photo (users) */
  photo_version?: string | null
  /** Asset classes: their own icon */
  icon?: string
}

export interface SearchCategory {
  key: string
  count: number
  results: SearchResult[]
}

export interface SearchResponse {
  q: string
  categories: SearchCategory[]
}

/** Shortest query searched */
export const MIN_QUERY = 2

export function searchAll(q: string, category = '') {
  return api<SearchResponse>(`/search/${queryString({ q, category })}`)
}

/** Each category of the API: the module it belongs to and whether a result has its own page */
const CATEGORY_MODULES: Record<
  string,
  { module: string; open?: (r: SearchResult) => RouteLocationRaw }
> = {
  efmv_analyses: {
    module: 'efmv-analyses',
    open: (r) => ({ name: 'efmv-analysis', params: { id: r.id } }),
  },
  average_prices: { module: 'average-prices' },
  business_entities: { module: 'business-entities' },
  assets: { module: 'inventory-assets' },
  users: { module: 'users' },
  warehouses: { module: 'warehouses' },
  verticals: { module: 'catalogs-verticals' },
  asset_classes: { module: 'catalogs-asset-classes' },
  manufacturers: { module: 'catalogs-manufacturers' },
}

const moduleNamed = (name: string) => visibleModules(true).find((m) => m.name === name)

/** The category's icon and title key (its module's); pages: their own. */
export function categoryInfo(key: string): { icon: string; titleKey: string } {
  if (key === 'pages') return { icon: 'mdi-file-document-outline', titleKey: 'search.pages' }
  const module = moduleNamed(CATEGORY_MODULES[key]?.module ?? '')
  return { icon: module?.icon ?? 'mdi-magnify', titleKey: module?.titleKey ?? key }
}

/** Where a result opens: its own page, else its module's grid searching for it. */
export function resultTarget(key: string, result: SearchResult): RouteLocationRaw {
  const category = CATEGORY_MODULES[key]
  if (category?.open) return category.open(result)
  return { name: category?.module ?? 'home', query: { search: result.search } }
}

// --- Pages ------------------------------------------------------------------------------------

export interface PageResult {
  name: string
  title: string
  /** "Pricing" / "Administration › Catalogs" */
  subtitle: string
  icon: string
}

type Translate = (key: string) => string

/** Letters without accents, lower case: "Ação" → "acao" */
export const fold = (text: string) => text.normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase()

/** The modules the user may open (and their own pages) whose name or app matches every word. */
export function searchPages(q: string, isAdmin: boolean, t: Translate): PageResult[] {
  const words = fold(q).split(/\s+/).filter(Boolean)
  if (!words.length) return []
  const pages: PageResult[] = visibleModules(isAdmin).map((module) => {
    const app = suiteApp(module.app)
    const where = [app ? appName(app, t) : '', module.section ? t(module.section) : '']
    return {
      name: module.name,
      title: t(module.titleKey),
      subtitle: where.filter(Boolean).join(' › '),
      icon: module.icon,
    }
  })
  pages.push(
    {
      name: 'notifications',
      title: t('menu.notifications'),
      subtitle: '',
      icon: 'mdi-bell-outline',
    },
    { name: 'settings', title: t('menu.settings'), subtitle: '', icon: 'mdi-cog-outline' },
  )
  return pages.filter((page) => {
    const text = fold(`${page.title} ${page.subtitle}`)
    return words.every((word) => text.includes(word))
  })
}

// --- Highlighting -------------------------------------------------------------------------------

/** The text in parts, the ones matching a word of the query marked (accents and case ignored). */
export function highlight(text: string, q: string): { text: string; match: boolean }[] {
  const words = fold(q)
    .split(/\s+/)
    .filter((w) => w.length >= MIN_QUERY)
  if (!text || !words.length) return [{ text, match: false }]
  // Folding keeps one letter per letter for Latin text, so positions line up
  const folded = fold(text)
  const marks = Array.from({ length: text.length }, () => false)
  if (folded.length === text.length) {
    for (const word of words) {
      let at = folded.indexOf(word)
      while (at >= 0) {
        marks.fill(true, at, at + word.length)
        at = folded.indexOf(word, at + word.length)
      }
    }
  }
  const parts: { text: string; match: boolean }[] = []
  for (let i = 0; i < text.length; i++) {
    const last = parts[parts.length - 1]
    if (last && last.match === marks[i]) last.text += text[i]
    else parts.push({ text: text[i]!, match: marks[i]! })
  }
  return parts
}
