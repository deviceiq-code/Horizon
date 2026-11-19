import { describe, expect, it } from 'vitest'
import { formatBytes } from '../bytes'

describe('formatBytes', () => {
  it('picks the unit and formats in the language', () => {
    expect(formatBytes(500, 'en')).toBe('0.5 kB')
    expect(formatBytes(850 * 1024, 'en')).toBe('850 kB')
    expect(formatBytes(2048, 'en')).toBe('2 kB')
    expect(formatBytes(2.5 * 1024 * 1024, 'en')).toBe('2.5 MB')
    expect(formatBytes(2.5 * 1024 * 1024, 'pt-BR')).toBe('2,5 MB')
  })
})
