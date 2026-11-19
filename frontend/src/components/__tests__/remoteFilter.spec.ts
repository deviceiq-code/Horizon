import { describe, expect, it } from 'vitest'

import { showInDropdown } from '../remoteFilter'

const MINING = { value: 4, title: 'Mining (Disabled)' }
const AGRO = { value: 5, title: 'Agribusiness' }
const ANA = { value: 7, title: 'Ana Souza' }

describe('showInDropdown', () => {
  it('shows everything while nothing is typed', () => {
    expect(showInDropdown(MINING, '', new Set())).toBe(true)
    expect(showInDropdown(MINING, '  ', new Set())).toBe(true)
  })

  it('hides a selected record that does not match the typed text', () => {
    // Regression: typing "agri" listed "Mining" first, and clicking it unselected it
    expect(showInDropdown(MINING, 'agri', new Set([AGRO.value]))).toBe(false)
    expect(showInDropdown(AGRO, 'agri', new Set([AGRO.value]))).toBe(true)
  })

  it('shows a selected record whose title matches the typed text', () => {
    expect(showInDropdown(MINING, 'min', new Set())).toBe(true)
    expect(showInDropdown(MINING, 'MIN', new Set())).toBe(true)
  })

  it('always shows what the server returned, even if matched by a hidden field', () => {
    // e.g. an account manager found by email: the title does not contain the text
    expect(showInDropdown(ANA, 'ana@example.com', new Set([ANA.value]))).toBe(true)
  })
})
