/**
 * Word Dictionary (a Smart Tool): words typed in a form become the dictionary's spelling when
 * the field is left — "ltda" or "Ltda" → "LTDA", "sa." or "s/a" → "S/A". Only whole words
 * (never part of one: "altdata" stays), in any case. The dictionary is shared by everyone and
 * kept by the administrators (Settings › App Settings › Administration); each user turns the
 * tool on or off (Settings › Smart Tools, `word_dictionary`).
 *
 * Fields: single-line text fields and text areas inside a form dialog — not e-mail, password,
 * web address or number fields, not pickers (their text is a search) nor fields marked
 * `data-no-dictionary`.
 */
import { api } from '@/api'

export interface DictionaryWord {
  id: number
  /** How it is always written ("S/A") */
  replacement: string
  /** Other ways it may be typed ("sa.", "s.a."); the replacement in any case counts too */
  variants: string[]
  updated_at: string
}

const URL = '/system/word-dictionary/'

export function listDictionaryWords() {
  return api<DictionaryWord[]>(URL)
}

/** Administrators only. Errors per field ({"variants": [...]}) */
export function saveDictionaryWord(
  word: Pick<DictionaryWord, 'replacement' | 'variants'> & { id?: number },
) {
  return word.id
    ? api<DictionaryWord>(`${URL}${word.id}/`, { method: 'PUT', body: JSON.stringify(word) })
    : api<DictionaryWord>(URL, { method: 'POST', body: JSON.stringify(word) })
}

export function deleteDictionaryWord(id: number) {
  return api<void>(`${URL}${id}/`, { method: 'DELETE' })
}

// --- Replacing (pure) ------------------------------------------------------------------------

/** A letter or a digit: what a whole word may not touch on either side */
const WORD_CHAR = '[\\p{L}\\p{N}]'
const escapeRegExp = (text: string) => text.replace(/[.*+?^${}()|[\]\\/]/g, '\\$&')

/** The text with every whole word of the dictionary written its way. */
export function applyDictionary(
  text: string,
  words: Pick<DictionaryWord, 'replacement' | 'variants'>[],
): string {
  const spelling = new Map<string, string>()
  for (const word of words) {
    for (const typed of [word.replacement, ...word.variants]) {
      const key = typed.trim().toLowerCase()
      if (key && !spelling.has(key)) spelling.set(key, word.replacement)
    }
  }
  if (!spelling.size || !text) return text
  // Longer ones first: "s.a." before "s.a"
  const alternatives = [...spelling.keys()].sort((a, b) => b.length - a.length).map(escapeRegExp)
  const pattern = new RegExp(
    `(?<!${WORD_CHAR})(?:${alternatives.join('|')})(?!${WORD_CHAR})`,
    'giu',
  )
  return text.replace(pattern, (match) => spelling.get(match.toLowerCase()) ?? match)
}

// --- The fields it applies to -----------------------------------------------------------------

const SKIPPED_INPUTS = new Set(['email', 'password', 'url', 'number', 'search', 'tel'])

export function appliesTo(
  target: EventTarget | null,
): target is HTMLInputElement | HTMLTextAreaElement {
  if (!(target instanceof HTMLInputElement || target instanceof HTMLTextAreaElement)) return false
  if (target.readOnly || target.disabled) return false
  if (target instanceof HTMLInputElement) {
    if (target.type !== 'text' || SKIPPED_INPUTS.has(target.type)) return false
    if (['numeric', 'decimal', 'email', 'url', 'tel'].includes(target.inputMode)) return false
  }
  // Pickers: what is typed there is a search, not a value
  if (target.closest('.v-autocomplete, .v-combobox, .v-select, [data-no-dictionary]')) return false
  // Only in forms (the dialogs that register things)
  return !!target.closest('.v-dialog form, form.v-form')
}

/** Installs the listener on the document; `enabled` and `words` are read each time a field is
 * left. Returns a cleanup. */
export function installWordDictionary(
  enabled: () => boolean,
  words: () => Pick<DictionaryWord, 'replacement' | 'variants'>[],
  root: Document = document,
) {
  const onFocusOut = (event: FocusEvent) => {
    const field = event.target
    if (!enabled() || !appliesTo(field)) return
    const replaced = applyDictionary(field.value, words())
    if (replaced === field.value) return
    field.value = replaced
    // The form's model follows (v-model listens to "input")
    field.dispatchEvent(new Event('input', { bubbles: true }))
  }
  root.addEventListener('focusout', onFocusOut)
  return () => root.removeEventListener('focusout', onFocusOut)
}
