/**
 * "Search the Internet" beside some text fields (WebSearchButton.vue): opens the user's search
 * engine (Settings → Smart Tools; a page cannot use the browser's default one) in a new tab.
 */
export type WebSearchEngine = 'google' | 'bing' | 'duckduckgo' | 'ecosia' | 'brave' | 'yahoo'

/** Each engine's name and its search address (the term goes at the end, encoded) */
export const WEB_SEARCH_ENGINES: Record<WebSearchEngine, { name: string; url: string }> = {
  google: { name: 'Google', url: 'https://www.google.com/search?q=' },
  bing: { name: 'Bing', url: 'https://www.bing.com/search?q=' },
  duckduckgo: { name: 'DuckDuckGo', url: 'https://duckduckgo.com/?q=' },
  ecosia: { name: 'Ecosia', url: 'https://www.ecosia.org/search?q=' },
  brave: { name: 'Brave Search', url: 'https://search.brave.com/search?q=' },
  yahoo: { name: 'Yahoo', url: 'https://search.yahoo.com/search?p=' },
}

export const isWebSearchEngine = (value: unknown): value is WebSearchEngine =>
  typeof value === 'string' && value in WEB_SEARCH_ENGINES

/** The search address for a term (spaces trimmed), or null when there is nothing to search. */
export function webSearchUrl(engine: WebSearchEngine, term: string): string | null {
  const text = term.trim()
  return text ? WEB_SEARCH_ENGINES[engine].url + encodeURIComponent(text) : null
}
