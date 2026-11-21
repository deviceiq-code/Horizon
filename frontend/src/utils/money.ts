/**
 * Money typed by the user and shown on screen. Values travel as decimal strings ("100000.50")
 * and are never turned into floats for calculations — the backend does all the math.
 */

/** Decimal separator of a UI language: "," for pt-br/es, "." for en. */
export function decimalSeparator(language: string): ',' | '.' {
  const parts = new Intl.NumberFormat(language).formatToParts(1.5)
  return parts.find((p) => p.type === 'decimal')?.value === ',' ? ',' : '.'
}

/**
 * What the user typed → canonical decimal string with at most `places` decimals, or null if it
 * is not a valid non-negative number. Thousands separators of the UI language are accepted:
 * pt-br "100.000,50" / en "100,000.50" → "100000.50". A lone separator followed by exactly
 * three digits is read as thousands ("1.500" in pt-br → "1500").
 */
export function parseMoney(text: string, language: string, places = 2): string | null {
  const value = text.trim().replace(/\s/g, '')
  if (!value) return null
  const decimal = decimalSeparator(language)
  const thousands = decimal === ',' ? '.' : ','
  const pattern =
    decimal === ',' ? /^(\d{1,3}(\.\d{3})+|\d+)(,\d+)?$/ : /^(\d{1,3}(,\d{3})+|\d+)(\.\d+)?$/
  if (!pattern.test(value)) {
    // Also accept the other style without thousands ("1500.5" typed in pt-br)
    if (/^\d+\.\d+$/.test(value) && decimal === ',') return withPlaces(value, places)
    return null
  }
  const canonical = value.split(thousands).join('').replace(decimal, '.')
  return withPlaces(canonical, places)
}

function withPlaces(canonical: string, places: number): string | null {
  const [, fraction = ''] = canonical.split('.')
  if (fraction.length > places) return null
  return canonical
}

/** "100000.5" + BRL → "R$ 100.000,50" (pt-br) / "R$100,000.50" (en). Display only. */
export function formatMoney(value: string, currency: string, language: string): string {
  // Number() only to format for display; values are never computed here
  return new Intl.NumberFormat(language, { style: 'currency', currency }).format(Number(value))
}

/** The currency's symbol in the UI language ("R$" for BRL; "$" for USD in en). */
export function currencySymbol(currency: string, language: string): string {
  const parts = new Intl.NumberFormat(language, { style: 'currency', currency }).formatToParts(0)
  return parts.find((part) => part.type === 'currency')?.value ?? currency
}

/** A decimal string as typed in the UI language ("100000.5" → "100.000,50" in pt-br). */
export function toInputMoney(value: string, language: string, places = 2): string {
  return new Intl.NumberFormat(language, {
    minimumFractionDigits: places,
    maximumFractionDigits: places,
  }).format(Number(value))
}

/**
 * A stored decimal shown in an input in the UI language, without trailing zeros beyond
 * `minPlaces` ("70.0000" → "70"; "55000.0000" with minPlaces 2 → "55.000,00" in pt-br).
 */
export function toInputNumber(
  value: string,
  language: string,
  minPlaces = 0,
  maxPlaces = 4,
): string {
  return new Intl.NumberFormat(language, {
    minimumFractionDigits: minPlaces,
    maximumFractionDigits: maxPlaces,
  }).format(Number(value))
}
