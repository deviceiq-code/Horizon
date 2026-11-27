/**
 * Remove Extra Spaces (a Smart Tool, `trim_spaces`, on by default): what is typed in a form
 * loses its spaces at the start and end and the repeated ones when the field is left —
 * " Test    of  String " → "Test of String". In text areas (descriptions, notes) the line
 * breaks stay; each line is tidied the same way. The same fields as the Word Dictionary
 * (`wordDictionary.ts::appliesTo`): text fields and text areas in forms, not pickers, e-mail,
 * password, address or number fields, nor fields marked `data-no-tidy`.
 */
import { appliesTo } from '@/wordDictionary'

/** The text without spaces at either end nor repeated ones (pure). Tabs and the non-breaking
 * space count as spaces; line breaks are kept, without spaces around them. */
export function tidySpaces(text: string): string {
  return text
    .split(/\r?\n/)
    .map((line) => line.replace(/[ \t ]+/g, ' ').trim())
    .join('\n')
    .trim()
}

/** Installs the listener on the document; `enabled` is read each time a field is left. Returns
 * a cleanup. */
export function installTidySpaces(enabled: () => boolean, root: Document = document) {
  const onFocusOut = (event: FocusEvent) => {
    const field = event.target
    if (!enabled() || !appliesTo(field, '[data-no-tidy]')) return
    const tidy = tidySpaces(field.value)
    if (tidy === field.value) return
    field.value = tidy
    // The form's model follows (v-model listens to "input")
    field.dispatchEvent(new Event('input', { bubbles: true }))
  }
  root.addEventListener('focusout', onFocusOut)
  return () => root.removeEventListener('focusout', onFocusOut)
}
