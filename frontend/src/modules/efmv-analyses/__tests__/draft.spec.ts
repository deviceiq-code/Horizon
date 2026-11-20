import { describe, expect, it } from 'vitest'
import {
  blankScenario,
  copyName,
  copyScenario,
  nextScenarioName,
  parseTerm,
  parseUnitValue,
  scenarioInput,
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

  it('names copies', () => {
    expect(copyName('Base', 'copy', ['Base'])).toBe('Base (copy)')
    expect(copyName('Base', 'copy', ['Base', 'base (copy)'])).toBe('Base (copy 2)')
  })

  it('sends the scenario without deleted prices', () => {
    const scenario = blankScenario(' Base ')
    scenario.term = '24'
    scenario.scope = ' Fleet '
    scenario.items = [
      { key: 1, average_price: 7, quantity: 2, unit_value: '100.000,50' },
      { key: 2, average_price: null, quantity: 1, unit_value: '' },
      { key: 3, average_price: 8, quantity: 1, unit_value: '' },
    ]
    expect(scenarioInput(scenario, 'pt-br')).toEqual({
      name: 'Base',
      term_months: 24,
      scope: 'Fleet',
      items: [
        { average_price: 7, quantity: 2, unit_value: '100000.50' },
        { average_price: 8, quantity: 1, unit_value: null },
      ],
    })
  })

  it('reads unit values typed in the UI language', () => {
    expect(parseUnitValue('1.500,25', 'pt-br')).toBe('1500.25')
    expect(parseUnitValue('1,500.25', 'en')).toBe('1500.25')
    expect(parseUnitValue('0', 'en')).toBeNull()
    expect(parseUnitValue('abc', 'en')).toBeNull()
  })

  it('copies a scenario with its own items', () => {
    const scenario = blankScenario('Base')
    scenario.items = [{ key: 1, average_price: 7, quantity: 2, unit_value: '10' }]
    const copy = copyScenario(scenario, 'Base (copy)')
    copy.items[0]!.quantity = 5
    expect(scenario.items[0]!.quantity).toBe(2)
    expect(copy.name).toBe('Base (copy)')
    expect(copy.key).not.toBe(scenario.key)
  })
})
