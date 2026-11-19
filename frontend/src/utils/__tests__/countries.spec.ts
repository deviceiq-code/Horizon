import { describe, expect, it } from 'vitest'

import { COUNTRY_CODES, countryName, countryOptions } from '../countries'

describe('countries', () => {
  it('has unique two-letter codes', () => {
    expect(COUNTRY_CODES.every((c) => /^[A-Z]{2}$/.test(c))).toBe(true)
    expect(new Set(COUNTRY_CODES).size).toBe(COUNTRY_CODES.length)
  })

  it('names countries in the UI language', () => {
    expect(countryName('BR', 'en')).toBe('Brazil')
    expect(countryName('BR', 'pt-br')).toBe('Brasil')
    expect(countryName('DE', 'es')).toBe('Alemania')
  })

  it('sorts options by name in the UI language', () => {
    const names = countryOptions('pt-br').map((c) => c.name)
    expect(names).toEqual([...names].sort((a, b) => a.localeCompare(b, 'pt-br')))
    expect(names).toContain('Estados Unidos')
  })
})
