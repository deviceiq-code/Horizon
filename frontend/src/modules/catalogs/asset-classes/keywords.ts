/**
 * Keywords relate assets to an asset class. They are kept as the backend stores them:
 * lowercase, single spaces, no duplicates. The backend normalizes them again on save.
 */
export const MAX_KEYWORDS = 30
export const MAX_KEYWORD_LENGTH = 50

/** "  Linha   AMARELA " → "linha amarela". */
export function normalizeKeyword(text: string): string {
  return text.split(/\s+/).filter(Boolean).join(' ').toLowerCase()
}

export type AddKeywordsResult =
  { keywords: string[]; error?: undefined } | { keywords: string[]; error: 'tooMany' | 'tooLong' }

/**
 * Add what the user typed (one keyword, or several separated by commas) to the list.
 * Blank and repeated keywords are ignored; the list keeps its order.
 */
export function addKeywords(current: readonly string[], typed: string): AddKeywordsResult {
  const keywords = [...current]
  for (const part of typed.split(',')) {
    const keyword = normalizeKeyword(part)
    if (!keyword || keywords.includes(keyword)) continue
    if (keyword.length > MAX_KEYWORD_LENGTH) return { keywords: [...current], error: 'tooLong' }
    if (keywords.length >= MAX_KEYWORDS) return { keywords: [...current], error: 'tooMany' }
    keywords.push(keyword)
  }
  return { keywords }
}
