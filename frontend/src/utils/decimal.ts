/**
 * Decimal values typed by the user. They stay strings (never floats) all the way to the API,
 * which validates them again; these helpers only guide the user while typing.
 */

/** "7,5" → "7.5"; trims spaces. Comma or dot are both accepted as decimal separator. */
export function normalizeDecimal(text: string): string {
  return text.trim().replace(',', '.')
}

/** True when `text` is a number from `min` to `max` with at most `places` decimal places. */
export function isDecimalInRange(text: string, min: number, max: number, places: number): boolean {
  const value = normalizeDecimal(text)
  const pattern = places > 0 ? new RegExp(`^\\d+(\\.\\d{1,${places}})?$`) : /^\d+$/
  if (!pattern.test(value)) return false
  // Comparing as a number is fine for a range check of a short validated literal
  const number = Number(value)
  return number >= min && number <= max
}
