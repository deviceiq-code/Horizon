import { describe, expect, it } from 'vitest'
import { parseTermInput } from '../termInput'

describe('parseTermInput', () => {
  it('reads a value or a percentage of the original value', () => {
    expect(parseTermInput('55,000.50', 'en')).toEqual({ mode: 'value', amount: '55000.50' })
    expect(parseTermInput('55.000,50', 'pt-br')).toEqual({ mode: 'value', amount: '55000.50' })
    expect(parseTermInput('70%', 'en')).toEqual({ mode: 'percent', amount: '70' })
    expect(parseTermInput(' 62,5 % ', 'pt-br')).toEqual({ mode: 'percent', amount: '62.5' })
    expect(parseTermInput('12.3456%', 'en')).toEqual({ mode: 'percent', amount: '12.3456' })
  })

  it('refuses what is neither', () => {
    for (const text of ['', '%', 'abc', '-5', '-5%', '1.234567%', '10.123']) {
      expect(parseTermInput(text, 'en')).toBeNull()
    }
  })
})
