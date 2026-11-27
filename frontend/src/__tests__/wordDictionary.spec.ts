import { afterEach, describe, expect, it } from 'vitest'

import { applyDictionary, appliesTo, installWordDictionary } from '@/wordDictionary'

const WORDS = [
  { replacement: 'LTDA', variants: [] },
  { replacement: 'S/A', variants: ['sa.', 's.a.', 's.a'] },
]

describe('Word Dictionary (Smart Tools)', () => {
  afterEach(() => {
    document.body.innerHTML = ''
  })

  it('writes whole words its way, in any case', () => {
    expect(applyDictionary('Acme ltda', WORDS)).toBe('Acme LTDA')
    expect(applyDictionary('Acme Ltda.', WORDS)).toBe('Acme LTDA.')
    expect(applyDictionary('Beta s/a', WORDS)).toBe('Beta S/A')
    expect(applyDictionary('Beta SA. e Gama s.a.', WORDS)).toBe('Beta S/A e Gama S/A')
    expect(applyDictionary('Delta S.A', WORDS)).toBe('Delta S/A')
  })

  it('never parts of words', () => {
    expect(applyDictionary('Altdata Ltdas', WORDS)).toBe('Altdata Ltdas')
    expect(applyDictionary('casa. Mesa.', WORDS)).toBe('casa. Mesa.')
    expect(applyDictionary('', WORDS)).toBe('')
    expect(applyDictionary('Acme ltda', [])).toBe('Acme ltda')
  })

  it("only in forms' text fields, not in e-mails, numbers or pickers", () => {
    document.body.innerHTML = `
      <div class="v-dialog"><form>
        <input id="name" type="text">
        <textarea id="notes"></textarea>
        <input id="email" type="email">
        <input id="value" type="text" inputmode="decimal">
        <div class="v-autocomplete"><input id="search" type="text"></div>
      </form></div>
      <input id="outside" type="text">`
    const get = (id: string) => document.getElementById(id)
    expect(appliesTo(get('name'))).toBe(true)
    expect(appliesTo(get('notes'))).toBe(true)
    for (const id of ['email', 'value', 'search', 'outside']) expect(appliesTo(get(id))).toBe(false)
  })

  it('replaces when the field is left (the form’s model follows), only when on', () => {
    document.body.innerHTML =
      '<div class="v-dialog"><form><input id="name" type="text"></form></div>'
    let on = true
    const remove = installWordDictionary(
      () => on,
      () => WORDS,
    )
    const field = document.getElementById('name') as HTMLInputElement
    const typed: string[] = []
    field.addEventListener('input', () => typed.push(field.value))
    field.value = 'acme ltda'
    field.dispatchEvent(new FocusEvent('focusout', { bubbles: true }))
    expect(field.value).toBe('acme LTDA')
    expect(typed).toEqual(['acme LTDA'])
    on = false
    field.value = 'beta s/a'
    field.dispatchEvent(new FocusEvent('focusout', { bubbles: true }))
    expect(field.value).toBe('beta s/a')
    remove()
  })
})
