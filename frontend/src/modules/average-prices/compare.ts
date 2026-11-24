/**
 * Comparing average prices side by side, as Battle Cards: each attribute is a row, and the
 * card(s) with the best value win it. Only values the API gave are compared (nothing is
 * calculated): at each term the highest eFMV % wins (keeps more of its value); among
 * ratings, the most stars. Terms or specifications a card lacks show as empty and never win.
 */
import type { AveragePriceDetail, PricePoint, SpecValue } from './api'

export const MAX_COMPARED = 3

export interface TermRow {
  term: number
  points: (PricePoint | null)[]
  /** Per card: it has the highest eFMV % at this term */
  best: boolean[]
}

export interface SpecRow {
  key: string
  label: string
  specs: (SpecValue | null)[]
  best: boolean[]
}

/** Which cards hold the highest value (none when fewer than two cards have one, or all tie). */
export function winners(values: (number | null)[]): boolean[] {
  const present = values.filter((v): v is number => v !== null && !Number.isNaN(v))
  if (present.length < 2) return values.map(() => false)
  const top = Math.max(...present)
  if (present.every((v) => v === top)) return values.map(() => false)
  return values.map((v) => v !== null && v === top)
}

/** Every term of any card, in order. */
export function termRows(items: AveragePriceDetail[]): TermRow[] {
  const terms = [...new Set(items.flatMap((i) => i.points.map((p) => p.term_months)))].sort(
    (a, b) => a - b,
  )
  return terms.map((term) => {
    const points = items.map((i) => i.points.find((p) => p.term_months === term) ?? null)
    return {
      term,
      points,
      best: winners(points.map((p) => (p ? Number(p.percent) : null))),
    }
  })
}

/** Every filled specification of any card (by label and unit), in the first card's order. */
export function specRows(items: AveragePriceDetail[]): SpecRow[] {
  const rows = new Map<string, SpecRow>()
  items.forEach((item, index) => {
    for (const spec of item.specs) {
      if (!spec.value) continue
      const key = `${spec.label.trim().toLowerCase()}|${spec.unit ?? ''}`
      let row = rows.get(key)
      if (!row) {
        row = { key, label: spec.label, specs: items.map(() => null), best: [] }
        rows.set(key, row)
      }
      row.specs[index] = spec
    }
  })
  return [...rows.values()].map((row) => ({
    ...row,
    best: row.specs.some((s) => s && s.kind !== 'rating')
      ? row.specs.map(() => false)
      : winners(row.specs.map((s) => (s ? Number(s.value) : null))),
  }))
}

/** How many attributes each card wins. */
export function wins(items: AveragePriceDetail[]): number[] {
  const rows = [...termRows(items), ...specRows(items)]
  return items.map((_, index) => rows.filter((row) => row.best[index]).length)
}
