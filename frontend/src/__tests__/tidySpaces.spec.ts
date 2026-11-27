import { afterEach, describe, expect, it } from 'vitest'

import { installTidySpaces, tidySpaces } from '@/tidySpaces'
import { installWordDictionary } from '@/wordDictionary'

describe('Remove Extra Spaces (Smart Tools)', () => {
  afterEach(() => {
    document.body.innerHTML = ''
  })

  it('removes spaces at either end and repeated ones; line breaks stay', () => {
    expect(tidySpaces(' Teste    de  String     ')).toBe('Teste de String')
    expect(tidySpaces('\tA  B ')).toBe('A B')
    expect(tidySpaces('  First   line  \n\n  second  line ')).toBe('First line\n\nsecond line')
    expect(tidySpaces('   ')).toBe('')
    expect(tidySpaces('Already tidy')).toBe('Already tidy')
  })

  it("tidies forms' text fields when left, while on; before the dictionary", () => {
    document.body.innerHTML = `
      <div class="v-dialog"><form>
        <input id="name" type="text">
        <input id="password" type="password">
        <input id="kept" type="text" data-no-tidy>
      </form></div>`
    let on = true
    const removeTidy = installTidySpaces(() => on)
    const removeDictionary = installWordDictionary(
      () => true,
      () => [{ replacement: 'LTDA', variants: [] }],
    )
    const leave = (id: string, value: string) => {
      const field = document.getElementById(id) as HTMLInputElement
      field.value = value
      field.dispatchEvent(new FocusEvent('focusout', { bubbles: true }))
      return field.value
    }
    const typed: string[] = []
    document.getElementById('name')!.addEventListener('input', (e) => {
      typed.push((e.target as HTMLInputElement).value)
    })
    expect(leave('name', '  Acme    ltda ')).toBe('Acme LTDA')
    expect(typed).toEqual(['Acme ltda', 'Acme LTDA'])
    expect(leave('password', ' my  secret ')).toBe(' my  secret ')
    expect(leave('kept', ' a  b ')).toBe(' a  b ')
    on = false
    expect(leave('name', ' Beta  ')).toBe(' Beta  ')
    removeTidy()
    removeDictionary()
  })
})
