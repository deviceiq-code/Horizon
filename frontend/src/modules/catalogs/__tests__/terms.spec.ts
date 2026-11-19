import { describe, expect, it } from 'vitest'

import { keepRecommended, normalizeTerms } from '../verticals/terms'

describe('normalizeTerms', () => {
  it('accepts any whole number of months, sorted and without duplicates', () => {
    expect(normalizeTerms([36, '12', ' 18 ', 12, 60], 360)).toEqual([12, 18, 36, 60])
  })

  it('drops values that are not valid terms', () => {
    expect(normalizeTerms(['abc', '', 0, -12, 12.5, '24', 361, 360], 360)).toEqual([24, 360])
  })
})

describe('keepRecommended', () => {
  it('keeps the recommended term while it is still allowed', () => {
    expect(keepRecommended([12, 24, 36], 24)).toBe(24)
  })

  it('picks the only remaining term when the recommended one was removed', () => {
    expect(keepRecommended([48], 36)).toBe(48)
  })

  it('asks to choose again when several terms remain', () => {
    expect(keepRecommended([12, 24], 36)).toBeNull()
    expect(keepRecommended([], 36)).toBeNull()
  })
})
