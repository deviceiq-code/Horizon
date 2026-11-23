import { describe, expect, it } from 'vitest'

import { ASSET_ICONS, DEFAULT_ASSET_ICON } from '../asset-classes/icons'
import { addKeywords, normalizeKeyword } from '@/utils/keywords'
import { numberToStars, previewAverage, starsToNumber } from '../remarketing/stars'

describe('stars', () => {
  it.each([
    ['3.5', 3.5],
    ['0.0', 0],
    ['5.0', 5],
  ])('%j → %d', (text, n) => expect(starsToNumber(text)).toBe(n))

  it('not filled in is 0 stars', () => {
    expect(starsToNumber(null)).toBe(0)
    expect(starsToNumber('')).toBe(0)
    expect(numberToStars(null)).toBe('0.0')
  })

  it.each([
    [3.5, '3.5'],
    [4, '4.0'],
    [0, '0.0'],
    [2.26, '2.5'], // rounds to the nearest half star
  ])('%d → %j', (n, text) => expect(numberToStars(n)).toBe(text))
})

describe('previewAverage (live, display only)', () => {
  it('is the simple average, zeros included', () => {
    expect(previewAverage(['3.5', '4.0', '0.0', '5.0'])).toBe(3.125)
    expect(previewAverage(['0.0', '0.0', '0.0'])).toBe(0)
  })

  it('counts missing ratings as 0', () => {
    expect(previewAverage(['4.0', ''])).toBe(2)
    expect(previewAverage([])).toBe(0)
  })
})

describe('keywords', () => {
  it('normalizes spaces and case', () => {
    expect(normalizeKeyword('  Linha   AMARELA ')).toBe('linha amarela')
  })

  it('adds one or several (comma-separated), skipping blanks and repeats', () => {
    expect(addKeywords(['escavadeira'], 'Hidráulica, , ESCAVADEIRA, esteira')).toEqual({
      keywords: ['escavadeira', 'hidráulica', 'esteira'],
    })
  })

  it('refuses more than 30 keywords or keywords longer than 50 characters', () => {
    const thirty = Array.from({ length: 30 }, (_, i) => `k${i}`)
    expect(addKeywords(thirty, 'one more').error).toBe('tooMany')
    expect(addKeywords([], 'x'.repeat(51)).error).toBe('tooLong')
    expect(addKeywords(['a'], 'x'.repeat(51)).keywords).toEqual(['a'])
  })
})

describe('icons', () => {
  it('offers unique MDI names, including the default', () => {
    expect(new Set(ASSET_ICONS).size).toBe(ASSET_ICONS.length)
    expect(ASSET_ICONS.every((i) => /^mdi-[a-z0-9]+(-[a-z0-9]+)*$/.test(i))).toBe(true)
    expect(ASSET_ICONS).toContain(DEFAULT_ASSET_ICON)
  })
})
