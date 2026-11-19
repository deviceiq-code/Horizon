/** File sizes for display ("0.5 kB", "850 kB", "2.4 MB"), in the UI language's number format. */

const UNITS = ['kilobyte', 'megabyte', 'gigabyte'] as const

export function formatBytes(bytes: number, locale: string): string {
  let value = bytes / 1024
  let unit = 0
  while (value >= 1024 && unit < UNITS.length - 1) {
    value /= 1024
    unit += 1
  }
  return new Intl.NumberFormat(locale, {
    style: 'unit',
    unit: UNITS[unit],
    unitDisplay: 'short',
    maximumFractionDigits: value < 10 ? 1 : 0,
  }).format(value)
}
