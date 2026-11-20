/** A stored specification value as shown: yes/no translated, stars, the number's unit. */
import type { SpecValue } from './api'

type Translate = (key: string) => string
type FormatNumber = (value: number, format: string) => string

export function specText(spec: SpecValue, t: Translate, n: FormatNumber): string {
  if (!spec.value) return '—'
  switch (spec.kind) {
    case 'boolean':
      return t(spec.value === 'true' ? 'common.yes' : 'common.no')
    case 'rating':
      return `★ ${n(Number(spec.value), 'rating')} / 5`
    case 'number':
      return spec.unit ? `${spec.value} ${spec.unit}` : spec.value
    default:
      return spec.value
  }
}
