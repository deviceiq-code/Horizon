import { describe, expect, it } from 'vitest'

import type { AveragePriceDetail } from '../api'
import { specRows, termRows, winners, wins } from '../compare'

function price(id: number, points: [number, string][], specs: [string, string, string][] = []) {
  return {
    id,
    points: points.map(([term_months, percent]) => ({
      term_months,
      mode: 'percent',
      amount: percent,
      value: percent,
      percent,
    })),
    specs: specs.map(([label, kind, value]) => ({
      key: label,
      label,
      kind,
      unit: '',
      required: false,
      value,
    })),
  } as unknown as AveragePriceDetail
}

describe('compare', () => {
  it('the highest value wins; ties and single values do not', () => {
    expect(winners([70, 75, null])).toEqual([false, true, false])
    expect(winners([70, 70])).toEqual([false, false])
    expect(winners([70, null])).toEqual([false, false])
    expect(winners([80, 80, 60])).toEqual([true, true, false])
  })

  it('terms of any card, in order; a missing term never wins', () => {
    const rows = termRows([
      price(1, [
        [24, '50'],
        [12, '70'],
      ]),
      price(2, [
        [12, '75'],
        [36, '40'],
      ]),
    ])
    expect(rows.map((r) => r.term)).toEqual([12, 24, 36])
    expect(rows[0]!.best).toEqual([false, true])
    expect(rows[1]!.points[1]).toBeNull()
    expect(rows[1]!.best).toEqual([false, false])
  })

  it('only ratings compete among the specifications', () => {
    const items = [
      price(
        1,
        [],
        [
          ['Stars', 'rating', '4.5'],
          ['Hours', 'number', '2500'],
        ],
      ),
      price(
        2,
        [],
        [
          ['Stars', 'rating', '3'],
          ['Hours', 'number', '900'],
        ],
      ),
    ]
    const rows = specRows(items)
    expect(rows.find((r) => r.label === 'Stars')!.best).toEqual([true, false])
    expect(rows.find((r) => r.label === 'Hours')!.best).toEqual([false, false])
    expect(wins(items)).toEqual([1, 0])
  })
})
