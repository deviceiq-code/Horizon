/** Text put into hand-written HTML (printed documents): &, <, >, " and ' escaped. */
export const escapeHtml = (text: string) => text.replace(/[&<>"']/g, (c) => `&#${c.charCodeAt(0)};`)

/** Print a whole HTML document through a hidden frame (the page itself is left alone). */
export function printDocument(html: string): void {
  const frame = document.createElement('iframe')
  frame.setAttribute('aria-hidden', 'true')
  frame.style.position = 'fixed'
  frame.style.width = '0'
  frame.style.height = '0'
  frame.style.border = '0'
  document.body.appendChild(frame)
  const doc = frame.contentDocument
  if (!doc || !frame.contentWindow) {
    frame.remove()
    return
  }
  doc.open()
  doc.write(html)
  doc.close()
  frame.contentWindow.focus()
  frame.contentWindow.print()
  // Removed once the print dialog has taken the document
  setTimeout(() => frame.remove(), 60_000)
}
