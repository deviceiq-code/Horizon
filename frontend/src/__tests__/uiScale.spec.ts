import { describe, expect, it } from 'vitest'
import { autoScale, isUiScale, uiScaleFactor } from '../uiScale'

describe('interface size', () => {
  it('follows the window width when automatic, within limits', () => {
    expect(autoScale(1024)).toBe(0.88)
    expect(autoScale(1366)).toBe(0.88)
    expect(autoScale(1600)).toBe(0.93)
    expect(autoScale(1920)).toBe(1)
    expect(autoScale(2240)).toBe(1.05)
    expect(autoScale(2560)).toBe(1.1)
    expect(autoScale(3840)).toBe(1.1)
  })

  it('keeps fixed sizes whatever the window', () => {
    expect(uiScaleFactor('small', 2560)).toBe(0.88)
    expect(uiScaleFactor('normal', 1366)).toBe(1)
    expect(uiScaleFactor('large', 1366)).toBe(1.1)
    expect(uiScaleFactor('auto', 1366)).toBe(0.88)
  })

  it('knows its choices', () => {
    expect(isUiScale('auto')).toBe(true)
    expect(isUiScale('huge')).toBe(false)
  })
})
