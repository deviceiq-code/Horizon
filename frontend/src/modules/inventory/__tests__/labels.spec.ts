import { describe, expect, it } from 'vitest'

import { barcodeSvg, labelsDocument, rangeLabels } from '../labels'

describe('labels', () => {
  it('a range gives one Horizon ID label per number, with its check digit', () => {
    expect(rangeLabels(1234, 1236).map((label) => label.code)).toEqual([
      'H000012344',
      'H000012351',
      'H000012369',
    ])
  })

  it('draws the barcode and escapes the texts', () => {
    expect(barcodeSvg('SP01-EST')).toContain('<rect')
    const html = labelsDocument([{ code: 'C000000018', title: 'Box <A&B>' }], 'Labels')
    expect(html).toContain('C000000018')
    expect(html).toContain('Box &#60;A&#38;B&#62;')
    expect(html).toContain('@page { size: 50mm 30mm')
  })
})
