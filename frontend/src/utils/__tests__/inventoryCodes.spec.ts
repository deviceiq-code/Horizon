import { describe, expect, it } from 'vitest'

import { code128Bars, code128Values } from '../code128'
import { formatCode, luhnDigit, parseCode } from '../inventoryCodes'

describe('inventory codes (same rules as the backend)', () => {
  it('computes the Luhn check digit', () => {
    expect(luhnDigit('7992739871')).toBe('3')
    expect(luhnDigit('00001234')).toBe('4')
    expect(formatCode('H', 1234)).toBe('H000012344')
    expect(formatCode('C', 1)).toBe('C000000018')
  })

  it('parses what a gun reads and catches a wrong digit', () => {
    expect(parseCode(' h000012344 ')).toEqual({ kind: 'asset', code: 'H000012344', valid: true })
    expect(parseCode('H000012345').valid).toBe(false)
    expect(parseCode('C000000018').kind).toBe('container')
    expect(parseCode('sp01-est-03')).toEqual({ kind: 'location', code: 'SP01-EST-03', valid: true })
    expect(parseCode('xyz').kind).toBe('unknown')
  })
})

describe('Code 128', () => {
  it('encodes with start B, the check symbol and stop', () => {
    // (104 + 48·1 + 42·2 + 42·3 + 17·4 + 18·5 + 19·6 + 35·7) mod 103 = 879 mod 103 = 55
    expect(code128Values('PJJ123C')).toEqual([104, 48, 42, 42, 17, 18, 19, 35, 55, 106])
  })

  it('draws 11 modules per symbol and 13 for the stop', () => {
    const { bars, width } = code128Bars('H000012344')
    // start + 10 characters + check = 12 symbols × 11 modules, + stop 13
    expect(width).toBe(12 * 11 + 13)
    expect(bars.length).toBe(12 * 3 + 4)
  })

  it('refuses characters outside Code 128 B', () => {
    expect(() => code128Values('ção')).toThrow('not supported')
  })
})
