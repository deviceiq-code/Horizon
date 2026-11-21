/** What the analysis page edits before saving (figures always come from the API). */
import { parseMoney, toInputMoney } from '@/utils/money'
import type { Scenario, ScenarioInput, ScenarioItem, ScenarioPreview } from './api'

export interface ItemDraft {
  /** Local key for v-for */
  key: number
  /** null: the average price was deleted (removed when saving) */
  average_price: number | null
  quantity: number
  /** Unit value as typed, in the UI language ("100.000,50" in pt-br) */
  unit_value: string
  /** eFMV value of one unit as typed; empty = the curve's value at the term */
  efmv_value: string
  /** A new row whose asset is not chosen yet (left out when saving) */
  pending?: boolean
}

export interface ScenarioDraft {
  key: number
  name: string
  /** As typed */
  term: string
  scope: string
  /** The assets it admits (sub_vertical null = the whole vertical) */
  vertical: number | null
  sub_vertical: number | null
  /** As the API showed it ("Industry / Yellow line"), until the list of verticals loads */
  scope_label: string | null
  items: ItemDraft[]
  /** Latest figures from the API, item by item in the same order as `items` */
  preview: ScenarioPreview | null
}

/** Validation errors of a scenario, as the API nests them. */
export interface ScenarioErrors {
  name?: string[]
  term_months?: string[]
  vertical?: string[]
  sub_vertical?: string[]
  scope?: string[]
  items?: Record<
    string,
    { average_price?: string[]; quantity?: string[]; unit_value?: string[]; efmv_value?: string[] }
  >
}

export const DEFAULT_TERM = 36
export const MAX_TERM = 360

let next = 0
export const newKey = () => ++next

export function blankScenario(name: string): ScenarioDraft {
  return {
    key: newKey(),
    name,
    term: String(DEFAULT_TERM),
    scope: '',
    vertical: null,
    sub_vertical: null,
    scope_label: null,
    items: [],
    preview: null,
  }
}

export function scenarioDraft(s: Scenario, language: string): ScenarioDraft {
  return {
    key: newKey(),
    name: s.name,
    term: String(s.term_months),
    scope: s.scope,
    vertical: s.vertical,
    sub_vertical: s.sub_vertical,
    scope_label: s.scope_label,
    items: s.items.map((i: ScenarioItem) => ({
      key: newKey(),
      average_price: i.average_price,
      quantity: i.quantity,
      unit_value: i.unit_value === null ? '' : toInputMoney(i.unit_value, language),
      // Typed only when it is not the curve's (that one stays the placeholder)
      efmv_value:
        i.efmv_value == null || i.efmv_from_curve ? '' : toInputMoney(i.efmv_value, language),
    })),
    preview: { items: s.items, totals: s.totals, has_expired: s.has_expired },
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

/** The unit value typed, as a canonical decimal string, or null when empty or invalid. */
export function parseUnitValue(text: string, language: string): string | null {
  const value = parseMoney(text, language)
  return value !== null && Number(value) > 0 ? value : null
}

/** The eFMV value typed (zero allowed), as a canonical decimal string, or null when empty or
 * invalid. */
export function parseEfmvValue(text: string, language: string): string | null {
  const value = parseMoney(text, language)
  return value !== null && Number(value) >= 0 ? value : null
}

/** Input for the API; assets whose price was deleted are left out. */
export function scenarioInput(s: ScenarioDraft, language: string): ScenarioInput {
  return {
    name: s.name.trim(),
    term_months: parseTerm(s.term) ?? 0,
    scope: s.scope.trim(),
    vertical: s.vertical,
    sub_vertical: s.sub_vertical,
    items: s.items
      .filter((i) => i.average_price !== null)
      .map((i) => ({
        average_price: i.average_price!,
        quantity: i.quantity,
        unit_value: parseUnitValue(i.unit_value, language),
        efmv_value: parseEfmvValue(i.efmv_value ?? '', language),
      })),
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
