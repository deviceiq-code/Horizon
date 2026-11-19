import { describe, expect, it } from 'vitest'

import { formatPostalCode, formatTaxId } from '../format'

describe('formatTaxId', () => {
  it.each([
    ['11222333000181', 'BR', '11.222.333/0001-81'],
    ['12ABC34501DE35', 'BR', '12.ABC.345/01DE-35'],
    ['11144477735', 'BR', '111.444.777-35'],
    ['123', 'BR', '123'],
    ['11222333000181', 'US', '11222333000181'],
  ])('%s (%s) → %s', (taxId, country, expected) => {
    expect(formatTaxId(taxId, country)).toBe(expected)
  })
})

describe('formatPostalCode', () => {
  it.each([
    ['13010100', 'BR', '13010-100'],
    ['1301', 'BR', '1301'],
    ['94105', 'US', '94105'],
  ])('%s (%s) → %s', (postalCode, country, expected) => {
    expect(formatPostalCode(postalCode, country)).toBe(expected)
  })
})
