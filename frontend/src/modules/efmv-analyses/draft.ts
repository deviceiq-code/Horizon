/** What the analysis page edits before saving (figures always come from the API). */
import { parseMoney, parseSignedMoney, toInputMoney } from '@/utils/money'
import type {
  ItemKind,
  Scenario,
  ScenarioInput,
  ScenarioItem,
  ScenarioItemInput,
  ScenarioPreview,
} from './api'

export interface ItemDraft {
  /** Local key for v-for */
  key: number
  /** Hardware (an average price), or software / a service of its own (absent: hardware) */
  kind?: ItemKind
  /** Software / service of its own: what it is (empty: "Software" / "Service") */
  description?: string
  /** Hardware: null = the average price was deleted (removed when saving) */
  average_price: number | null
  quantity: number
  /** Unit value as typed, in the UI language ("100.000,50" in pt-br) */
  unit_value: string
  /** eFMV value of one unit as typed; empty = the curve's value at the term */
  efmv_value: string
  /** A new row whose asset is not chosen yet (left out when saving) */
  pending?: boolean
  /** Hardware: its service (SV) attached, shown as a row under it; at most one */
  service?: ServiceDraft | null
  /** Hardware: its software (SW) attached, shown as a row under it; at most one */
  software?: ServiceDraft | null
}

/** What is attached to a hardware line: a name, a value per unit (money or "8%") added to or
 * deducted from it; software also its eFMV as typed (empty: 0). */
export interface ServiceDraft {
  name: string
  /** As typed, in the UI language ("1.000,00" or "8%") */
  value: string
  mode: ServiceMode
  /** Software only: one unit at the end of the term, as typed (money or "10%"; empty: 0) */
  efmv?: string
}

/** The attachments of a hardware line, in the order they show under it */
export const ATTACHMENTS = ['software', 'service'] as const
export type AttachmentKey = (typeof ATTACHMENTS)[number]

/** Software or a service of its own (not attached to hardware) */
export const isStandalone = (item: { kind?: ItemKind }) => !!item.kind && item.kind !== 'hw'

/** Hardware whose average price was deleted (left out of the totals; removed when saving) */
export const isDeleted = (item: ItemDraft) =>
  !isStandalone(item) && item.average_price === null && !item.pending

export type ServiceMode = 'add' | 'deduct'

export interface ScenarioDraft {
  key: number
  name: string
  /** As typed */
  term: string
  scope: string
  items: ItemDraft[]
  /** Smart Tools: the scope written from the assets (the API's latest); shown in gray while the
   * scope is empty, and what an empty scope means */
  suggestion: string
  /** Latest figures from the API, item by item in the same order as `items` */
  preview: ScenarioPreview | null
}

/** Validation errors of a scenario, as the API nests them. */
export interface ScenarioErrors {
  name?: string[]
  term_months?: string[]
  scope?: string[]
  items?: Record<
    string,
    {
      average_price?: string[]
      quantity?: string[]
      unit_value?: string[]
      efmv_value?: string[]
      /** The attachments' own errors, or by field ({"name": [...]}) */
      service?: string[] | Record<string, string[]>
      software?: string[] | Record<string, string[]>
    }
  >
}

export const DEFAULT_TERM = 36
export const MAX_TERM = 360

let next = 0
export const newKey = () => ++next

export function blankScenario(name = ''): ScenarioDraft {
  return {
    key: newKey(),
    name,
    term: String(DEFAULT_TERM),
    scope: '',
    items: [],
    suggestion: '',
    preview: null,
  }
}

export function scenarioDraft(s: Scenario, language: string): ScenarioDraft {
  return {
    key: newKey(),
    name: s.name,
    term: String(s.term_months),
    scope: s.scope,
    items: s.items.map((i: ScenarioItem) => ({
      key: newKey(),
      kind: i.kind ?? 'hw',
      description: i.description ?? '',
      average_price: i.average_price,
      quantity: i.quantity,
      unit_value: i.unit_value === null ? '' : toInputMoney(i.unit_value, language),
      // Typed only when it is not the curve's (that one stays the placeholder); a service's
      // is always 0 (nothing typed); software's 0 stays the placeholder
      efmv_value:
        i.efmv_value == null ||
        i.efmv_from_curve ||
        (i.kind && i.kind !== 'hw' && Number(i.efmv_value) === 0)
          ? ''
          : toInputMoney(i.efmv_value, language),
      service: i.service
        ? {
            name: i.service.name,
            value: toInputMoney(i.service.value, language),
            mode: i.service.mode,
          }
        : null,
      software: i.software
        ? {
            name: i.software.name,
            value: toInputMoney(i.software.value, language),
            mode: i.software.mode,
            efmv:
              i.software.efmv_value && Number(i.software.efmv_value) !== 0
                ? toInputMoney(i.software.efmv_value, language)
                : '',
          }
        : null,
    })),
    suggestion: s.scope_suggestion ?? '',
    preview: {
      items: s.items,
      totals: s.totals,
      has_expired: s.has_expired,
      scope_suggestion: s.scope_suggestion,
    },
  }
}

/** A copy with a new name (for "Duplicate"). */
export function copyScenario(s: ScenarioDraft, name: string): ScenarioDraft {
  return {
    ...s,
    key: newKey(),
    name,
    items: s.items.map((i) => ({
      ...i,
      key: newKey(),
      service: i.service && { ...i.service },
      software: i.software && { ...i.software },
    })),
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

/** The eFMV value typed, as a canonical decimal string, or null when empty or invalid. Zero
 * and negative values are allowed (negative: no resale value and a disposal cost). */
export function parseEfmvValue(text: string, language: string): string | null {
  return parseSignedMoney(text, language)
}

/** The eFMV typed as a percentage of the unit value ("25%", "12,5 %" in pt-br), as a canonical
 * decimal string ("25", "12.5"), or null when it is not one. The API turns it into a value. */
export function parseEfmvPercent(text: string, language: string): string | null {
  const match = /^(.*?)\s*%\s*$/.exec(text.trim())
  if (!match) return null
  // Negative allowed (a disposal cost); up to the server's 5 places of percentages
  return parseSignedMoney(match[1]!, language, 5)
}

/** Whether what was typed in an eFMV cell is acceptable: empty, a value or a percentage. */
export function isEfmvInput(text: string, language: string): boolean {
  return (
    !text.trim() ||
    parseEfmvValue(text, language) !== null ||
    parseEfmvPercent(text, language) !== null
  )
}

/**
 * A service's value as typed: money or a percentage of the asset's value ("8%"), zero or more
 * (empty = zero); null when it is neither.
 */
export function parseServiceInput(
  text: string,
  language: string,
): { value: string } | { percent: string } | null {
  if (!text.trim()) return { value: '0' }
  const percent = /^(.*?)\s*%\s*$/.exec(text.trim())
  // A percentage: up to the server's 5 places
  const parsed = parseMoney(percent ? percent[1]! : text, language, percent ? 5 : 2)
  if (parsed === null || Number(parsed) < 0) return null
  return percent ? { percent: parsed } : { value: parsed }
}

/**
 * How many units of each kind, by quantity: HW — the hardware lines (with an average price) —,
 * SW and SV — of their own, plus those attached to hardware (as many as their hardware). A
 * quantity being typed that is not a whole number yet counts as 0.
 */
export function assetCounts(
  items: {
    kind?: ItemKind
    average_price: number | null
    quantity: number
    service?: unknown
    software?: unknown
  }[],
): { hw: number; sw: number; sv: number } {
  const units = (i: { quantity: number }) =>
    Number.isInteger(i.quantity) && i.quantity > 0 ? i.quantity : 0
  const sum = (list: typeof items) => list.reduce((total, i) => total + units(i), 0)
  const hardware = items.filter((i) => !isStandalone(i) && i.average_price !== null)
  return {
    hw: sum(hardware),
    sw: sum(items.filter((i) => i.kind === 'sw')) + sum(hardware.filter((i) => !!i.software)),
    sv: sum(items.filter((i) => i.kind === 'sv')) + sum(hardware.filter((i) => !!i.service)),
  }
}

/** An attachment as the API takes it; not named: the placeholder's name */
function attachmentInput(a: ServiceDraft, language: string, defaultName: string) {
  return {
    name: a.name.trim() || defaultName,
    mode: a.mode,
    ...(parseServiceInput(a.value, language) ?? { value: '0' }),
  }
}

/** Input for the API; hardware whose price was deleted and rows not chosen yet are left out. */
export function scenarioInput(
  s: ScenarioDraft,
  language: string,
  serviceName = 'Service',
  softwareName = 'Software',
): ScenarioInput {
  return {
    name: s.name.trim(),
    term_months: parseTerm(s.term) ?? 0,
    scope: s.scope.trim(),
    items: s.items
      .filter((i) => isStandalone(i) || i.average_price !== null)
      .map((i): ScenarioItemInput => {
        const efmvPercent = parseEfmvPercent(i.efmv_value ?? '', language)
        if (isStandalone(i)) {
          return {
            kind: i.kind,
            // Not described: the placeholder ("Software" / "Service") is enough
            description: (i.description ?? '').trim(),
            quantity: i.quantity,
            unit_value: parseUnitValue(i.unit_value, language),
            efmv_value: i.kind === 'sw' ? parseEfmvValue(i.efmv_value ?? '', language) : null,
            ...(i.kind === 'sw' && efmvPercent !== null && { efmv_percent: efmvPercent }),
          }
        }
        return {
          average_price: i.average_price!,
          quantity: i.quantity,
          unit_value: parseUnitValue(i.unit_value, language),
          efmv_value: parseEfmvValue(i.efmv_value ?? '', language),
          // "25%": a percentage of the unit value, turned into a value by the API
          ...(efmvPercent !== null && { efmv_percent: efmvPercent }),
          // Its attachments, when it has them (none sent: none kept)
          ...(i.service && { service: attachmentInput(i.service, language, serviceName) }),
          ...(i.software && {
            software: {
              ...attachmentInput(i.software, language, softwareName),
              efmv_value: parseEfmvValue(i.software.efmv ?? '', language),
              ...(parseEfmvPercent(i.software.efmv ?? '', language) !== null && {
                efmv_percent: parseEfmvPercent(i.software.efmv ?? '', language)!,
              }),
            },
          }),
        }
      }),
  }
}

/**
 * The official name of a scenario: its term and the name given, if any ("36 Months - Desktops",
 * "60 Months"). `months` translates the term ("36 Months"); the tab and the API show the same.
 */
export function scenarioTitle(
  term: string,
  name: string,
  months: (count: number) => string,
  untitled: string,
): string {
  const count = parseTerm(term)
  const parts = [count === null ? '' : months(count), name.trim().replace(/\s+/g, ' ')]
  return parts.filter(Boolean).join(' - ') || untitled
}

/** What makes two official names equal: the term and the name, ignoring case and spaces. */
export function titleKey(term: string, name: string): string {
  return `${parseTerm(term) ?? term.trim()}|${name.trim().replace(/\s+/g, ' ').toLowerCase()}`
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
