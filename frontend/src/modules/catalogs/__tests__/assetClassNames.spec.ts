import { describe, expect, it } from 'vitest'
import { englishPlural } from '../asset-classes/names'

describe('asset class names', () => {
  it('suggests the English plural as the backend does', () => {
    expect(englishPlural('Laptop')).toBe('Laptops')
    expect(englishPlural('3D Printer')).toBe('3D Printers')
    expect(englishPlural('Battery')).toBe('Batteries')
    expect(englishPlural('Display')).toBe('Displays')
    expect(englishPlural('Switch')).toBe('Switches')
    expect(englishPlural('Accessories')).toBe('Accessories')
  })
})
