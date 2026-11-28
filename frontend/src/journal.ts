/**
 * The Home's journal (backend `system/journal.py`): what happened lately — counts only — in the
 * modules the user may open, and what is new in each version. The period is the user's
 * `journal_days` preference (Settings › Appearance).
 */
import { api } from '@/api'
import { MODULES, type AppModule } from '@/modules'

export interface JournalEvent {
  /** "<category>.<what>" — e.g. "efmv_analyses.created" */
  key: string
  count: number
}

export interface Release {
  version: string
  /** ISO date */
  date: string
  /** In the user's language */
  notes: string[]
}

export interface Journal {
  days: number
  since: string
  events: JournalEvent[]
  version: string
  /** The latest ones, or all of them (`allReleases`) */
  releases: Release[]
  releases_total: number
}

/** `allReleases`: the whole history of versions (the System Journal's "Read More") */
export function getJournal(allReleases = false) {
  return api<Journal>(`/system/journal/${allReleases ? '?releases=all' : ''}`)
}

/** The module each event's category opens (its main route name) */
const EVENT_MODULES: Record<string, string> = {
  efmv_analyses: 'efmv-analyses',
  average_prices: 'average-prices',
  assets: 'inventory-assets',
  receiving_lots: 'inventory-receiving',
  inspections: 'inventory-inspections',
  disposals: 'inventory-disposals-list',
  transfers: 'inventory-transfers',
  business_entities: 'business-entities',
  manufacturers: 'catalogs-manufacturers',
  asset_classes: 'catalogs-asset-classes',
  asset_models: 'catalogs-asset-models',
  users: 'users',
}

/** The module of an event ("efmv_analyses.created" → eFMV Analyses), for its icon and page */
export function eventModule(key: string): AppModule | undefined {
  const name = EVENT_MODULES[key.split('.')[0] ?? '']
  return MODULES.find((module) => module.name === name)
}
