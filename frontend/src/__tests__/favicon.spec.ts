import { afterEach, describe, expect, it } from 'vitest'

import { applyFavicon, faviconSvg } from '@/favicon'

describe("the tab's icon follows the theme", () => {
  afterEach(() => {
    document.head.innerHTML = ''
  })

  it('draws the mark on the brand color and points every icon link to it', () => {
    expect(faviconSvg('#FF2063')).toContain('fill="#FF2063"')
    document.head.innerHTML =
      '<link rel="icon" href="/favicon.svg" type="image/svg+xml"><link rel="icon" href="/favicon.ico" sizes="48x48">'
    applyFavicon('#FF2063')
    const links = [...document.querySelectorAll<HTMLLinkElement>('link[rel="icon"]')]
    expect(links).toHaveLength(2)
    for (const link of links) {
      expect(decodeURIComponent(link.href)).toContain('fill="#FF2063"')
      expect(link.hasAttribute('sizes')).toBe(false)
    }
    // Not a color: left as it is
    applyFavicon('url(x)')
    expect(decodeURIComponent(links[0]!.href)).toContain('#FF2063')
  })
})
