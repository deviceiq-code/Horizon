/**
 * Numbers and money as the user wants them (Settings → Numbers and Currency), saved with the
 * account: the number format ("auto" follows the interface's language; the others fix the
 * thousands and decimal separators), the decimal places of percentages (1–5, every percentage
 * shown follows it) and how a currency is shown — always, on the left of value fields: its
 * symbol or its code (values keep their own currency). Every number on screen goes through here: `$n` / `useNumberFormat`
 * and the money helpers (utils/money.ts), which call `numberLocale()`.
 */
import { reactive } from 'vue'

export type NumberFormat = 'auto' | 'dot_comma' | 'comma_dot' | 'space_comma'
export type CurrencyDisplay = 'symbol' | 'code'

export const NUMBER_FORMATS: readonly NumberFormat[] = [
  'auto',
  'dot_comma',
  'comma_dot',
  'space_comma',
]
export const CURRENCY_DISPLAYS: readonly CurrencyDisplay[] = ['symbol', 'code']

/** Decimal places of percentages: from 1 to 5 (2 by default) */
export const MIN_PERCENT_PLACES = 1
export const MAX_PERCENT_PLACES = 5
export const isPercentPlaces = (value: unknown): value is number =>
  Number.isInteger(value) &&
  (value as number) >= MIN_PERCENT_PLACES &&
  (value as number) <= MAX_PERCENT_PLACES

/** The currencies a user can choose as theirs (ISO 4217; backend accounts.models.CURRENCIES) */
export const CURRENCIES = [
  'BRL', 'USD', 'EUR', 'GBP', 'JPY', 'CNY', 'CHF', 'CAD', 'AUD', 'MXN',
  'ARS', 'CLP', 'COP', 'PEN', 'UYU', 'PYG', 'BOB', 'INR', 'ZAR',
] as const // prettier-ignore
export type Currency = (typeof CURRENCIES)[number]

export const isCurrency = (value: unknown): value is Currency =>
  (CURRENCIES as readonly unknown[]).includes(value)

/** A currency's name, symbol and code in the interface's language ("Real brasileiro", "R$"). */
export function currencyInfo(code: string, language: string) {
  let name = code
  try {
    name = new Intl.DisplayNames(language, { type: 'currency' }).of(code) ?? code
  } catch {
    /* Intl.DisplayNames unavailable: the code */
  }
  const parts = new Intl.NumberFormat(language, {
    style: 'currency',
    currency: code,
  }).formatToParts(0)
  const symbol = parts.find((part) => part.type === 'currency')?.value ?? code
  return { code, name, symbol }
}

export const isNumberFormat = (value: unknown): value is NumberFormat =>
  (NUMBER_FORMATS as readonly unknown[]).includes(value)
export const isCurrencyDisplay = (value: unknown): value is CurrencyDisplay =>
  (CURRENCY_DISPLAYS as readonly unknown[]).includes(value)

/** A locale whose separators are the format's ("1.234,56", "1,234.56", "1 234,56"). */
const LOCALES: Record<Exclude<NumberFormat, 'auto'>, string> = {
  dot_comma: 'pt-BR',
  comma_dot: 'en-US',
  space_comma: 'fr-FR',
}

/** In use (set from the preferences store); reactive, so what is shown follows a change. */
export const numberSettings = reactive<{
  format: NumberFormat
  currency: CurrencyDisplay
  percentPlaces: number
}>({
  format: 'auto',
  currency: 'symbol',
  percentPlaces: 2,
})

/** The locale numbers are written in: the interface's language, or the chosen format's. */
export function numberLocale(language: string): string {
  const format = numberSettings.format
  return format === 'auto' ? language : LOCALES[format]
}

/** The app's named number formats (as vue-i18n's `$n(value, key)`). */
export const NAMED_NUMBER_FORMATS = {
  decimal: { style: 'decimal', minimumFractionDigits: 2, maximumFractionDigits: 2 },
  /** Percentages: the decimal places are the user's (`percentPlaces`) */
  percent: { style: 'percent', minimumFractionDigits: 2, maximumFractionDigits: 2 },
  /** 0–10 ratings, always with one decimal: 7.5 / 7,5 */
  rating: { style: 'decimal', minimumFractionDigits: 1, maximumFractionDigits: 1 },
  /** A percentage already in 0–100 scale ("68.75" → 68,75), shown next to a % sign */
  percentValue: { style: 'decimal', minimumFractionDigits: 2, maximumFractionDigits: 2 },
} as const satisfies Record<string, Intl.NumberFormatOptions>

export type NumberKey = keyof typeof NAMED_NUMBER_FORMATS

/** A number in one of the named formats, with the user's separators. */
export function formatNumber(value: number, key: NumberKey | undefined, language: string): string {
  const options: Intl.NumberFormatOptions = key ? { ...NAMED_NUMBER_FORMATS[key] } : {}
  if (key === 'percent' || key === 'percentValue') {
    options.minimumFractionDigits = options.maximumFractionDigits = numberSettings.percentPlaces
  }
  return new Intl.NumberFormat(numberLocale(language), options).format(value)
}
