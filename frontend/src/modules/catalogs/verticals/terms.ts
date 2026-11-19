/**
 * Turn what the user typed/picked in the terms field into a clean list of months:
 * whole numbers from 1 to `max`, without duplicates, ascending. Anything else is dropped.
 */
export function normalizeTerms(values: readonly (string | number)[], max: number): number[] {
  const months = values
    .map((v) => (typeof v === 'number' ? v : Number(String(v).trim())))
    .filter((n) => Number.isInteger(n) && n >= 1 && n <= max)
  return [...new Set(months)].sort((a, b) => a - b)
}

/**
 * The recommended term after the allowed terms changed: kept if still allowed; when it was
 * removed, the only remaining term is picked, otherwise the user must choose again (null).
 */
export function keepRecommended(allowed: readonly number[], recommended: number | null) {
  if (recommended !== null && allowed.includes(recommended)) return recommended
  return allowed.length === 1 ? allowed[0]! : null
}
