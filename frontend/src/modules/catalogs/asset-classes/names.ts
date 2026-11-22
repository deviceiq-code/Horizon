/**
 * Names of asset classes: English (name and plural, required) and, per other language, an
 * optional name and plural (empty: English). The plural suggested while typing follows the same
 * rule as the backend (catalogs/names.py::english_plural); it can be corrected.
 */
export function englishPlural(name: string): string {
  const text = name.trim()
  if (!text) return text
  const at = text.lastIndexOf(' ')
  const head = at >= 0 ? text.slice(0, at + 1) : ''
  const last = text.slice(at + 1)
  const lower = last.toLowerCase()
  let plural: string
  if (lower.endsWith('s')) plural = last
  else if (
    lower.endsWith('y') &&
    last.length > 1 &&
    !'aeiou'.includes(lower.charAt(lower.length - 2))
  )
    plural = `${last.slice(0, -1)}ies`
  else if (/(x|z|ch|sh)$/.test(lower)) plural = `${last}es`
  else plural = `${last}s`
  return head + plural
}

export interface ClassTranslation {
  name: string
  plural: string
}
