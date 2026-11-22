import { describe, expect, it } from 'vitest'
import { formatDate } from '../dateFormat'

// 22 November 2026, 15:05 local time
const value = new Date(2026, 10, 22, 15, 5)

describe('date and time formats', () => {
  it('follows the language when automatic', () => {
    expect(formatDate(value, 'short', 'pt-br', 'auto', 'auto')).toBe('22/11/2026')
    expect(formatDate(value, 'short', 'en', 'auto', 'auto')).toBe('11/22/2026')
    expect(formatDate(value, 'dateTime', 'pt-br', 'auto', 'auto')).toBe('22/11/2026, 15:05')
  })

  it('fixes the order of day, month and year', () => {
    expect(formatDate(value, 'short', 'en', 'dmy', 'auto')).toBe('22/11/2026')
    expect(formatDate(value, 'short', 'pt-br', 'mdy', 'auto')).toBe('11/22/2026')
    expect(formatDate(value, 'short', 'es', 'ymd', 'auto')).toBe('2026-11-22')
  })

  it('fixes the clock', () => {
    expect(formatDate(value, 'dateTime', 'en', 'ymd', '24h')).toBe('2026-11-22, 15:05')
    expect(formatDate(value, 'dateTime', 'pt-br', 'dmy', '12h')).toMatch(
      /^22\/11\/2026, 3:05\s?PM$/i,
    )
  })
})
