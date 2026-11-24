import { describe, expect, it } from 'vitest'

import type { SpecField } from '../api'
import { importFields } from '../templateImport'

const field = (key: string, label: string, kind: SpecField['kind'] = 'text'): SpecField => ({
  key,
  label,
  kind,
  unit: '',
  required: false,
  options: [],
})

describe('importing a template', () => {
  const current = [field('hours', 'Operating Hours', 'number'), field('color', 'Color')]
  const other = [field('h2', ' operating  hours ', 'number'), field('cab', 'Cab', 'boolean')]

  it('adds only the fields not here yet (by name), as new fields', () => {
    const result = importFields(current, other, 'add')
    expect(result.fields.map((f) => f.label)).toEqual(['Operating Hours', 'Color', 'Cab'])
    expect(result.fields[2]!.key).toBe('')
    expect([result.added, result.skipped]).toEqual([1, 1])
  })

  it('replaces, keeping the identity of fields with the same name', () => {
    const result = importFields(current, other, 'replace')
    expect(result.fields.map((f) => [f.key, f.label.trim()])).toEqual([
      ['hours', 'operating  hours'],
      ['', 'Cab'],
    ])
    expect(result.added).toBe(1)
  })
})
