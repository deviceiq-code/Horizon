import { describe, expect, it } from 'vitest'
import {
  assetCounts,
  blankScenario,
  copyName,
  copyScenario,
  nextScenarioName,
  isEfmvInput,
  parseEfmvPercent,
  parseEfmvValue,
  parseServiceInput,
  parseTerm,
  parseUnitValue,
  scenarioInput,
  scenarioTitle,
  titleKey,
} from '../draft'

describe('eFMV analysis draft', () => {
  it('parses whole terms from 1 to 360', () => {
    expect(parseTerm(' 36 ')).toBe(36)
    expect(parseTerm('360')).toBe(360)
    expect(parseTerm('0')).toBeNull()
    expect(parseTerm('361')).toBeNull()
    expect(parseTerm('12.5')).toBeNull()
    expect(parseTerm('')).toBeNull()
  })

  it('names new scenarios with the first free number', () => {
    expect(nextScenarioName('Scenario', ['Scenario 1'])).toBe('Scenario 2')
    expect(nextScenarioName('Scenario', ['Base', 'scenario 3', 'Other'])).toBe('Scenario 4')
  })

  it('calls a scenario by its term and name', () => {
    const months = (n: number) => (n === 1 ? '1 Month' : `${n} Months`)
    expect(scenarioTitle('36', ' Desktops ', months, 'Untitled')).toBe('36 Months - Desktops')
    expect(scenarioTitle('60', '', months, 'Untitled')).toBe('60 Months')
    expect(scenarioTitle('1', 'A  B', months, 'Untitled')).toBe('1 Month - A B')
    expect(scenarioTitle('', 'Desktops', months, 'Untitled')).toBe('Desktops')
    expect(scenarioTitle('x', '', months, 'Untitled')).toBe('Untitled')
    expect(titleKey(' 36', 'Desktops ')).toBe(titleKey('36', ' desktops'))
    expect(titleKey('36', '')).not.toBe(titleKey('60', ''))
  })

  it('names copies', () => {
    expect(copyName('Base', 'copy', ['Base'])).toBe('Base (copy)')
    expect(copyName('Base', 'copy', ['Base', 'base (copy)'])).toBe('Base (copy 2)')
  })

  it('sends the scenario without deleted prices', () => {
    const scenario = blankScenario(' Base ')
    scenario.term = '24'
    scenario.scope = ' Fleet '
    scenario.items = [
      { key: 1, average_price: 7, quantity: 2, unit_value: '100.000,50', efmv_value: '0' },
      { key: 2, average_price: null, quantity: 1, unit_value: '', efmv_value: '' },
      { key: 3, average_price: 8, quantity: 1, unit_value: '', efmv_value: '42.500' },
      { key: 4, average_price: 9, quantity: 1, unit_value: '', efmv_value: '12,5%' },
    ]
    expect(scenarioInput(scenario, 'pt-br')).toEqual({
      name: 'Base',
      term_months: 24,
      scope: 'Fleet',
      items: [
        { average_price: 7, quantity: 2, unit_value: '100000.50', efmv_value: '0' },
        { average_price: 8, quantity: 1, unit_value: null, efmv_value: '42500' },
        { average_price: 9, quantity: 1, unit_value: null, efmv_value: null, efmv_percent: '12.5' },
      ],
    })
  })

  it('reads unit values typed in the UI language', () => {
    expect(parseUnitValue('1.500,25', 'pt-br')).toBe('1500.25')
    expect(parseUnitValue('1,500.25', 'en')).toBe('1500.25')
    expect(parseUnitValue('0', 'en')).toBeNull()
    expect(parseUnitValue('abc', 'en')).toBeNull()
    // eFMV values may be zero
    expect(parseEfmvValue('0', 'en')).toBe('0')
    // Negative: a disposal cost
    expect(parseEfmvValue('-1.500,25', 'pt-br')).toBe('-1500.25')
    expect(parseEfmvValue('abc', 'en')).toBeNull()
    // …or a percentage of the unit value
    expect(parseEfmvPercent('25%', 'en')).toBe('25')
    expect(parseEfmvPercent(' 12,5 % ', 'pt-br')).toBe('12.5')
    expect(parseEfmvPercent('25', 'en')).toBeNull()
    expect(parseEfmvPercent('-5%', 'en')).toBe('-5')
    expect(isEfmvInput('25%', 'en') && isEfmvInput('', 'en') && isEfmvInput('10', 'en')).toBe(true)
    expect(isEfmvInput('%', 'en')).toBe(false)
  })

  it('reads a service as a value or a percentage, zero or more', () => {
    expect(parseServiceInput('1.500,25', 'pt-br')).toEqual({ value: '1500.25' })
    expect(parseServiceInput('8%', 'en')).toEqual({ percent: '8' })
    expect(parseServiceInput('', 'en')).toEqual({ value: '0' })
    expect(parseServiceInput('-5', 'en')).toBeNull()
    expect(parseServiceInput('abc', 'en')).toBeNull()
    const scenario = blankScenario()
    scenario.items = [
      {
        key: 1,
        average_price: 7,
        quantity: 2,
        unit_value: '',
        efmv_value: '',
        service: { name: ' Warranty ', value: '10%', mode: 'deduct' },
      },
    ]
    expect(scenarioInput(scenario, 'en').items[0]!.service).toEqual({
      name: 'Warranty',
      mode: 'deduct',
      percent: '10',
    })
  })

  it('counts units (quantities) of assets (HW) and of their services (SV) apart', () => {
    expect(
      assetCounts([
        { average_price: 7, quantity: 10, service: { name: 'Warranty' } },
        { average_price: 8, quantity: 3, service: null },
        { average_price: null, quantity: 1 }, // a row without an asset yet
        { average_price: 9, quantity: Number.NaN }, // a quantity being typed
      ]),
    ).toEqual({ hw: 13, sw: 0, sv: 10 })
  })

  it('copies a scenario with its own items', () => {
    const scenario = blankScenario('Base')
    scenario.items = [{ key: 1, average_price: 7, quantity: 2, unit_value: '10', efmv_value: '' }]
    const copy = copyScenario(scenario, 'Base (copy)')
    copy.items[0]!.quantity = 5
    expect(scenario.items[0]!.quantity).toBe(2)
    expect(copy.name).toBe('Base (copy)')
    expect(copy.key).not.toBe(scenario.key)
  })
})
