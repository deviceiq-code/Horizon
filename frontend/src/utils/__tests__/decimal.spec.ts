import { describe, expect, it } from 'vitest'

import { isDecimalInRange, normalizeDecimal } from '../decimal'

describe('normalizeDecimal', () => {
  it('accepts comma or dot and trims', () => {
    expect(normalizeDecimal(' 7,5 ')).toBe('7.5')
    expect(normalizeDecimal('7.5')).toBe('7.5')
  })
})

describe('isDecimalInRange (rating 0–10, one decimal)', () => {
  it.each(['0', '10', '7', '7.5', '7,5', '0.1', '9.9', '10.0'])('accepts %j', (text) => {
    expect(isDecimalInRange(text, 0, 10, 1)).toBe(true)
  })

  it.each(['', '-1', '10.1', '11', '7.55', '7,55', 'abc', '1e1', '.5', '5.'])(
    'rejects %j',
    (text) => {
      expect(isDecimalInRange(text, 0, 10, 1)).toBe(false)
    },
  )

  it('with zero places accepts only whole numbers', () => {
    expect(isDecimalInRange('7', 0, 10, 0)).toBe(true)
    expect(isDecimalInRange('7.5', 0, 10, 0)).toBe(false)
  })
})
