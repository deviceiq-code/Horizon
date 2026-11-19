/**
 * Remarketing star ratings (0–5, half steps) travel as decimal strings ("3.5") and are edited
 * with v-rating (numbers). Not filled in = 0 stars.
 */

/** "3.5" → 3.5; empty → 0. */
export function starsToNumber(value: string | null | undefined): number {
  if (value === null || value === undefined || value === '') return 0
  return Number(value)
}

/** 3.5 → "3.5"; 4 → "4.0"; nothing → "0.0". Rounds to the nearest half star. */
export function numberToStars(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) return '0.0'
  return (Math.round(value * 2) / 2).toFixed(1)
}

/**
 * Average shown live while editing, before saving. Display only: the official value is the
 * API's `remarketing_average` (backend catalogs.ratings.average_stars, same simple average).
 */
export function previewAverage(values: readonly (string | null | undefined)[]): number {
  if (!values.length) return 0
  return values.reduce((sum, v) => sum + starsToNumber(v), 0) / values.length
}
