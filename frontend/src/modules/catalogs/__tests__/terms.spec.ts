import { describe, expect, it } from 'vitest'

import { keepRecommended, parseTerm } from '../verticals/terms'

describe('parseTerm', () => {
  it.each([
    ['18', 18],
    [' 36 ', 36],
    ['1', 1],
    ['360', 360],
  ])('accepts %j → %d', (text, months) => {
    expect(parseTerm(text, 360)).toBe(months)
  })

  it.each(['', '  ', '0', '361', '12.5', '-12', '+12', '1e2', 'abc', '12 months'])(
    'rejects %j',
    (text) => {
      expect(parseTerm(text, 360)).toBeNull()
    },
  )
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
