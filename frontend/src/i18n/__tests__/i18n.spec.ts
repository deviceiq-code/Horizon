import { readdirSync, readFileSync, statSync } from 'node:fs'
import { join, resolve } from 'node:path'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { LANGUAGES, detectLanguage, normalizeLanguage } from '@/i18n'
import en from '@/i18n/locales/en'
import es from '@/i18n/locales/es'
import ptBR from '@/i18n/locales/pt-br'
import { MODULES } from '@/modules'

// Vitest runs with frontend/ as the working directory (vitest.config.ts → root)
const SRC_ROOT = resolve('src')

/** List the "a.b.c" keys of a messages object. */
function keys(obj: object, prefix = ''): string[] {
  return Object.entries(obj).flatMap(([k, v]) =>
    typeof v === 'object' && v !== null ? keys(v, `${prefix}${k}.`) : [`${prefix}${k}`],
  )
}

function sourceFiles(dir: string): string[] {
  return readdirSync(dir).flatMap((name) => {
    const path = join(dir, name)
    if (statSync(path).isDirectory()) return name === '__tests__' ? [] : sourceFiles(path)
    return /\.(vue|ts)$/.test(name) ? [path] : []
  })
}

describe('translation files', () => {
  const reference = keys(en).sort()

  it.each([
    ['pt-br', ptBR],
    ['es', es],
  ])('%s has exactly the same keys as en', (_code, messages) => {
    expect(keys(messages).sort()).toEqual(reference)
  })

  it('every key used in t()/$t() in the code exists', () => {
    const used = new Set<string>()
    for (const file of sourceFiles(SRC_ROOT)) {
      const content = readFileSync(file, 'utf-8')
      for (const m of content.matchAll(/\$?\bt\(\s*['"]([\w.]+)['"]/g)) used.add(m[1]!)
    }
    expect(used.size).toBeGreaterThan(0)
    const missing = [...used].filter((k) => !reference.includes(k))
    expect(missing).toEqual([])
  })

  it('every module title key exists (keys passed as variables are not found above)', () => {
    const missing = MODULES.map((m) => m.titleKey).filter((k) => !reference.includes(k))
    expect(missing).toEqual([])
  })

  it('every language in the list has a unique code', () => {
    expect(new Set(LANGUAGES.map((l) => l.code)).size).toBe(LANGUAGES.length)
  })
})

describe('normalizeLanguage', () => {
  it.each([
    ['pt-BR', 'pt-br'],
    ['pt-PT', 'pt-br'],
    ['pt', 'pt-br'],
    ['en-US', 'en'],
    ['EN', 'en'],
    ['es-AR', 'es'],
    ['fr-FR', null],
  ])('%s → %s', (input, expected) => {
    expect(normalizeLanguage(input)).toBe(expected)
  })
})

describe('detectLanguage', () => {
  afterEach(() => {
    localStorage.clear()
    vi.restoreAllMocks()
  })

  it('prefers the language previously picked in this browser', () => {
    localStorage.setItem('horizon.language', 'es')
    vi.spyOn(navigator, 'languages', 'get').mockReturnValue(['pt-BR'])
    expect(detectLanguage()).toBe('es')
  })

  it('uses the first supported browser language', () => {
    vi.spyOn(navigator, 'languages', 'get').mockReturnValue(['fr-FR', 'pt-BR', 'en-GB'])
    expect(detectLanguage()).toBe('pt-br')
  })

  it('falls back to English when nothing is supported', () => {
    vi.spyOn(navigator, 'languages', 'get').mockReturnValue(['fr-FR', 'de'])
    expect(detectLanguage()).toBe('en')
  })

  it('ignores an invalid value stored in the browser', () => {
    localStorage.setItem('horizon.language', 'xx')
    vi.spyOn(navigator, 'languages', 'get').mockReturnValue(['es-ES'])
    expect(detectLanguage()).toBe('es')
  })
})
