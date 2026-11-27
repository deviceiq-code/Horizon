import { createPinia, setActivePinia } from 'pinia'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { setLanguage } from '@/i18n'
import { inBody, mountWithPlugins, settle } from '@/test-utils'
import * as dictionaryApi from '@/wordDictionary'
import WordDictionarySection from '../settings/WordDictionarySection.vue'

vi.mock('@/wordDictionary', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@/wordDictionary')>()),
  listDictionaryWords: vi.fn<typeof dictionaryApi.listDictionaryWords>(),
  saveDictionaryWord: vi.fn<typeof dictionaryApi.saveDictionaryWord>(),
  deleteDictionaryWord: vi.fn<typeof dictionaryApi.deleteDictionaryWord>(),
}))
const api = vi.mocked(dictionaryApi)

const LTDA = { id: 1, replacement: 'LTDA', variants: [], updated_at: '' }
const SA = { id: 2, replacement: 'S/A', variants: ['sa.'], updated_at: '' }

describe('the word dictionary (App Settings)', () => {
  beforeEach(() => {
    setLanguage('en')
    setActivePinia(createPinia())
    api.listDictionaryWords.mockResolvedValue([LTDA, SA])
  })
  afterEach(() => {
    vi.clearAllMocks()
    document.body.innerHTML = ''
  })

  it('lists, adds, tries and removes words', async () => {
    const wrapper = mountWithPlugins(WordDictionarySection)
    await settle()
    expect(document.querySelectorAll('[data-testid="dictionary-word"]')).toHaveLength(2)
    // Each word shows its own spelling (any case) among the ways to type it, even with no others
    const words = document.querySelectorAll('[data-testid="dictionary-word"]')
    const chips = (row: Element) =>
      Array.from(row.querySelectorAll('[data-testid^="list-item"]')).map((c) =>
        c.textContent!.trim(),
      )
    expect(chips(words[0]!)).toEqual(['ltda'])
    expect(chips(words[1]!)).toEqual(['s/a', 'sa.'])
    expect(words[0]!.querySelector('[data-testid="list-item-fixed"] .v-chip__close')).toBeNull()
    // Try it: what a text becomes
    const trial = inBody('[data-testid="dictionary-try"] input') as HTMLInputElement
    trial.value = 'Acme ltda, Beta sa.'
    trial.dispatchEvent(new Event('input'))
    await settle()
    expect(inBody('[data-testid="dictionary-tried"]')!.textContent).toContain('Acme LTDA, Beta S/A')
    // A new word: saved when its spelling is left
    api.saveDictionaryWord.mockResolvedValue({
      id: 3,
      replacement: 'ME',
      variants: [],
      updated_at: '',
    })
    ;(inBody('[data-testid="dictionary-add"]') as HTMLButtonElement).click()
    await settle()
    const fields = document.querySelectorAll<HTMLInputElement>(
      '[data-testid="dictionary-replacement"] input',
    )
    const added = fields[fields.length - 1]!
    added.value = 'ME'
    added.dispatchEvent(new Event('input'))
    await settle()
    added.dispatchEvent(new Event('blur'))
    await settle()
    expect(api.saveDictionaryWord).toHaveBeenCalledWith({
      id: undefined,
      replacement: 'ME',
      variants: [],
    })
    api.deleteDictionaryWord.mockResolvedValue()
    document.querySelectorAll<HTMLButtonElement>('[data-testid="dictionary-remove"]')[0]!.click()
    await settle()
    expect(api.deleteDictionaryWord).toHaveBeenCalledWith(1)
    expect(document.querySelectorAll('[data-testid="dictionary-word"]')).toHaveLength(2)
    wrapper.unmount()
  })
})
