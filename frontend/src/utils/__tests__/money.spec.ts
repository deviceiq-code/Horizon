import { describe, expect, it } from 'vitest'

import {
  decimalSeparator,
  formatMoney,
  parseMoney,
  toInputMoney,
  toInputNumber,
  currencySymbol,
  parseSignedMoney,
} from '../money'

describe('decimalSeparator', () => {
  it('follows the UI language', () => {
    expect(decimalSeparator('pt-br')).toBe(',')
    expect(decimalSeparator('es')).toBe(',')
    expect(decimalSeparator('en')).toBe('.')
  })
})

describe('parseMoney', () => {
  it.each([
    ['100000', '100000'],
    ['100.000', '100000'], // thousands
    ['100.000,50', '100000.50'],
    ['1.234.567,8', '1234567.8'],
    ['100000,5', '100000.5'],
    [' 2.500 ', '2500'],
    ['1500.75', '1500.75'], // dot decimal still understood
  ])('pt-br %j → %j', (text, expected) => {
    expect(parseMoney(text, 'pt-br')).toBe(expected)
  })

  it.each([
    ['100,000.50', '100000.50'],
    ['100000.5', '100000.5'],
    ['1,500', '1500'],
  ])('en %j → %j', (text, expected) => {
    expect(parseMoney(text, 'en')).toBe(expected)
  })

  it.each(['', 'abc', '-10', '10,00,0', '1.00.0', '12,345', '1e5'])('pt-br rejects %j', (text) => {
    expect(parseMoney(text, 'pt-br')).toBeNull()
  })

  it('rejects more decimals than allowed', () => {
    expect(parseMoney('10,555', 'pt-br')).toBeNull()
    expect(parseMoney('10,5555', 'pt-br', 4)).toBe('10.5555')
  })
})

describe('formatting for display', () => {
  it('formats money in the UI language', () => {
    expect(formatMoney('100000.5', 'BRL', 'pt-br')).toMatch(/R\$\s100\.000,50/)
    expect(formatMoney('100000.5', 'BRL', 'en')).toMatch(/R\$\s?100,000\.50/)
  })

  it('shows a value the way the user would type it', () => {
    expect(toInputMoney('100000.5', 'pt-br')).toBe('100.000,50')
    expect(toInputMoney('70', 'en', 4)).toBe('70.0000')
  })
})

describe('toInputNumber', () => {
  it('drops trailing zeros beyond the minimum', () => {
    expect(toInputNumber('70.0000', 'pt-br')).toBe('70')
    expect(toInputNumber('42.5000', 'pt-br')).toBe('42,5')
    expect(toInputNumber('55000.0000', 'pt-br', 2)).toBe('55.000,00')
  })

  it('round-trips through parseMoney', () => {
    expect(parseMoney(toInputNumber('1234567.89', 'pt-br', 2), 'pt-br')).toBe('1234567.89')
    expect(parseMoney(toInputNumber('1234567.89', 'en', 2), 'en')).toBe('1234567.89')
  })

  it('gives the currency symbol in the UI language', () => {
    expect(currencySymbol('BRL', 'pt-br')).toBe('R$')
    expect(currencySymbol('BRL', 'en')).toBe('R$')
    expect(currencySymbol('USD', 'en')).toBe('$')
  })

  it('reads signed money', () => {
    expect(parseSignedMoney('-1.500,25', 'pt-br')).toBe('-1500.25')
    expect(parseSignedMoney(' - 10', 'en')).toBe('-10')
    expect(parseSignedMoney('−3', 'en')).toBe('-3')
    expect(parseSignedMoney('-0', 'en')).toBe('0')
    expect(parseSignedMoney('25', 'en')).toBe('25')
    expect(parseSignedMoney('--1', 'en')).toBeNull()
    expect(parseMoney('-1', 'en')).toBeNull()
  })
})
