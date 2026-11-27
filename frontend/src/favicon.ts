/**
 * The browser tab's icon in the theme's `brand` color (the same drawing as the side menu's
 * BrandIcon and public/favicon.svg, which stays the default before the theme is known).
 */
const MARK =
  '<path fill="#FFFFFF" d="M42.9 32.3 L57.2 31.7 L44.3 37.9 Z M40.5 29.0 L49.2 26.8 L43.6 33.9 Z M37.1 26.8 L48.0 17.5 L41.7 30.3 Z M33.2 25.7 L38.7 18.6 L38.6 27.6 Z M29.1 26.0 L32.0 12.0 L34.9 26.0 Z M25.4 27.6 L25.3 18.6 L30.8 25.7 Z M22.3 30.3 L16.0 17.5 L26.9 26.8 Z M20.4 33.9 L14.8 26.8 L23.5 29.0 Z M19.7 37.9 L6.8 31.7 L21.1 32.3 Z"/>' +
  '<path fill="#FFFFFF" d="M22 38 A10 10 0 0 1 42 38 Z"/>' +
  '<path fill="#FFFFFF" d="M6 50 Q32 32 58 50 Q32 41 6 50 Z"/>'

/** The icon as an SVG document on a rounded square of `color` */
export function faviconSvg(color: string): string {
  return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64" width="64" height="64"><rect width="64" height="64" rx="14" fill="${color}"/>${MARK}</svg>`
}

/** Point the page's icons (SVG and the ICO fallback) to the icon in `color`. */
export function applyFavicon(color: string, root: Document = document): void {
  if (!/^#[0-9a-f]{3,8}$/i.test(color)) return
  const href = `data:image/svg+xml,${encodeURIComponent(faviconSvg(color))}`
  const links = root.querySelectorAll<HTMLLinkElement>('link[rel="icon"]')
  if (!links.length) {
    const link = root.createElement('link')
    link.rel = 'icon'
    root.head.appendChild(link)
    link.type = 'image/svg+xml'
    link.href = href
    return
  }
  for (const link of Array.from(links)) {
    link.type = 'image/svg+xml'
    link.removeAttribute('sizes')
    link.href = href
  }
}
