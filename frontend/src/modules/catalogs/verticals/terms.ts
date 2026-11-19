/**
 * A term typed by the user, in months: a whole number from 1 to `max`, else null.
 * Accepts surrounding spaces ("  18 "), rejects decimals, signs and text.
 */
export function parseTerm(text: string, max: number): number | null {
  const trimmed = text.trim()
  if (!/^\d+$/.test(trimmed)) return null
  const months = Number(trimmed)
  return months >= 1 && months <= max ? months : null
}

/**
 * The recommended term after the allowed terms changed: kept if still allowed; when it was
 * removed, the only remaining term is picked, otherwise the user must choose again (null).
 */
export function keepRecommended(allowed: readonly number[], recommended: number | null) {
  if (recommended !== null && allowed.includes(recommended)) return recommended
  return allowed.length === 1 ? allowed[0]! : null
}
