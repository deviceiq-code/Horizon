/** What the analysis page edits before saving (figures always come from the API). */
import type { Scenario, ScenarioInput, ScenarioItem, ScenarioPreview } from './api'

export interface ItemDraft {
  /** Local key for v-for */
  key: number
  /** null: the average price was deleted (removed when saving) */
  average_price: number | null
  quantity: number
}

export interface ScenarioDraft {
  key: number
  name: string
  /** As typed */
  term: string
  scope: string
  items: ItemDraft[]
  /** Latest figures from the API, item by item in the same order as `items` */
  preview: ScenarioPreview | null
}

/** Validation errors of a scenario, as the API nests them. */
export interface ScenarioErrors {
  name?: string[]
  term_months?: string[]
  scope?: string[]
  items?: Record<string, { average_price?: string[]; quantity?: string[] }>
}

export const DEFAULT_TERM = 36
export const MAX_TERM = 360

let next = 0
export const newKey = () => ++next

export function blankScenario(name: string): ScenarioDraft {
  return { key: newKey(), name, term: String(DEFAULT_TERM), scope: '', items: [], preview: null }
}

export function scenarioDraft(s: Scenario): ScenarioDraft {
  return {
    key: newKey(),
    name: s.name,
    term: String(s.term_months),
    scope: s.scope,
    items: s.items.map((i: ScenarioItem) => ({
      key: newKey(),
      average_price: i.average_price,
      quantity: i.quantity,
    })),
    preview: { items: s.items, totals: s.totals },
  }
}

/** A copy with a new name (for "Duplicate"). */
export function copyScenario(s: ScenarioDraft, name: string): ScenarioDraft {
  return {
    ...s,
    key: newKey(),
    name,
    items: s.items.map((i) => ({ ...i, key: newKey() })),
    preview: s.preview && { ...s.preview, items: [...s.preview.items] },
  }
}

/** The term typed, or null when it is not a whole number from 1 to 360. */
export function parseTerm(text: string): number | null {
  const value = text.trim()
  if (!/^\d+$/.test(value)) return null
  const term = Number(value)
  return term >= 1 && term <= MAX_TERM ? term : null
}

/** Input for the API; assets whose price was deleted are left out. */
export function scenarioInput(s: ScenarioDraft): ScenarioInput {
  return {
    name: s.name.trim(),
    term_months: parseTerm(s.term) ?? 0,
    scope: s.scope.trim(),
    items: s.items
      .filter((i) => i.average_price !== null)
      .map((i) => ({ average_price: i.average_price!, quantity: i.quantity })),
  }
}

/** First name "Scenario N" not used yet. */
export function nextScenarioName(base: string, taken: string[]): string {
  const used = new Set(taken.map((n) => n.trim().toLowerCase()))
  for (let n = taken.length + 1; ; n++) {
    const name = `${base} ${n}`
    if (!used.has(name.toLowerCase())) return name
  }
}

/** Name of a copy: "Base (copy)", then "Base (copy 2)"… */
export function copyName(name: string, copyWord: string, taken: string[]): string {
  const used = new Set(taken.map((n) => n.trim().toLowerCase()))
  for (let n = 1; ; n++) {
    const candidate = `${name.trim()} (${copyWord}${n > 1 ? ` ${n}` : ''})`
    if (!used.has(candidate.toLowerCase())) return candidate
  }
}
