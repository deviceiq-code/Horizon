import { describe, expect, it } from 'vitest'

import { i18n, setLanguage } from '@/i18n'
import { categoryInfo, highlight, resultTarget, searchPages, type SearchResult } from '@/search'

const t = (key: string) => i18n.global.t(key)

const result = (over: Partial<SearchResult> = {}): SearchResult => ({
  id: 7,
  title: 'TransDeere',
  subtitle: '',
  meta: '',
  badge: null,
  search: 'Transportes Deere Ltda',
  amount: null,
  ...over,
})

describe('centralized search', () => {
  it('marks the words searched for, ignoring accents and letter case', () => {
    expect(highlight('Precificação Média', 'media')).toEqual([
      { text: 'Precificação ', match: false },
      { text: 'Média', match: true },
    ])
    expect(highlight('John Deere 648L', 'deere 648')).toEqual([
      { text: 'John ', match: false },
      { text: 'Deere', match: true },
      { text: ' ', match: false },
      { text: '648', match: true },
      { text: 'L', match: false },
    ])
    // One letter: nothing marked
    expect(highlight('Dell', 'd')).toEqual([{ text: 'Dell', match: false }])
  })

  it('a category is a module: its icon and title', () => {
    expect(categoryInfo('customers').titleKey).toBe('customers.title')
    expect(categoryInfo('efmv_analyses').icon).toMatch(/^mdi-/)
    expect(categoryInfo('pages')).toEqual({
      icon: 'mdi-file-document-outline',
      titleKey: 'search.pages',
    })
  })

  it("a result opens its own page, else its module's grid searching for it", () => {
    expect(resultTarget('efmv_analyses', result({ id: 3 }))).toEqual({
      name: 'efmv-analysis',
      params: { id: 3 },
    })
    expect(resultTarget('customers', result())).toEqual({
      name: 'customers',
      query: { search: 'Transportes Deere Ltda' },
    })
  })

  it('pages by their names in the UI language; administrators only for theirs', () => {
    setLanguage('pt-br')
    const titles = (q: string, admin: boolean) => searchPages(q, admin, t).map((p) => p.title)
    expect(titles('average', false)).toContain('Average Prices')
    expect(titles('notif', false)).toEqual(['Notificações'])
    expect(titles('usuarios', false)).toEqual([])
    expect(titles('usuarios', true)).toContain('Usuários')
    setLanguage('en')
  })
})
