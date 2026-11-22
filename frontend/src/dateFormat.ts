/**
 * Dates and times as the user wants them (Settings → Date and Time): "auto" follows the
 * interface's language (Intl); the others fix the order of day, month and year and the clock.
 * Pure functions here; components use `useDateFormat()` (composables/useDateFormat.ts).
 */

export type DateFormat = 'auto' | 'dmy' | 'mdy' | 'ymd'
export type TimeFormat = 'auto' | '24h' | '12h'
export type DateKind = 'short' | 'dateTime'

export const DATE_FORMATS: readonly DateFormat[] = ['auto', 'dmy', 'mdy', 'ymd']
export const TIME_FORMATS: readonly TimeFormat[] = ['auto', '24h', '12h']

export const isDateFormat = (value: unknown): value is DateFormat =>
  (DATE_FORMATS as readonly unknown[]).includes(value)
export const isTimeFormat = (value: unknown): value is TimeFormat =>
  (TIME_FORMATS as readonly unknown[]).includes(value)

function datePart(value: Date, language: string, format: DateFormat): string {
  const options = { year: 'numeric', month: '2-digit', day: '2-digit' } as const
  if (format === 'auto') return new Intl.DateTimeFormat(language, options).format(value)
  const parts = new Intl.DateTimeFormat('en-US', options).formatToParts(value)
  const part = (type: string) => parts.find((p) => p.type === type)!.value
  const [day, month, year] = [part('day'), part('month'), part('year')]
  if (format === 'dmy') return `${day}/${month}/${year}`
  if (format === 'mdy') return `${month}/${day}/${year}`
  return `${year}-${month}-${day}`
}

function timePart(value: Date, language: string, format: TimeFormat): string {
  if (format === '12h') {
    return new Intl.DateTimeFormat(language, {
      hour: 'numeric',
      minute: '2-digit',
      hour12: true,
    }).format(value)
  }
  return new Intl.DateTimeFormat(language, {
    hour: '2-digit',
    minute: '2-digit',
    ...(format === '24h' && { hourCycle: 'h23' as const }),
  }).format(value)
}

/** A date ("short") or a date and time ("dateTime") in the user's formats. */
export function formatDate(
  value: Date,
  kind: DateKind,
  language: string,
  dateFormat: DateFormat,
  timeFormat: TimeFormat,
): string {
  const date = datePart(value, language, dateFormat)
  return kind === 'short' ? date : `${date}, ${timePart(value, language, timeFormat)}`
}
