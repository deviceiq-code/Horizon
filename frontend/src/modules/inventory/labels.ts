/**
 * Labels for assets, containers and locations: the code as a Code 128 barcode (what the guns
 * read) and in text, with a title and a subtitle. One label per page of 50 × 30 mm — the usual
 * roll of a thermal label printer; the browser's print dialog picks the printer.
 */
import { escapeHtml, printDocument } from '@/utils/html'
import { code128Bars } from '@/utils/code128'
import { formatCode } from '@/utils/inventoryCodes'

export interface Label {
  code: string
  title?: string
  subtitle?: string
}

const escape = escapeHtml

/** The barcode as SVG (quiet zones of 10 modules on each side). */
export function barcodeSvg(code: string): string {
  const { bars, width } = code128Bars(code)
  const total = width + 20
  const rects = bars
    .map(([x, w]) => `<rect x="${x + 10}" y="0" width="${w}" height="40"/>`)
    .join('')
  return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${total} 40" preserveAspectRatio="none" class="bars">${rects}</svg>`
}

/** A whole printable document, one label per page. */
export function labelsDocument(labels: Label[], documentTitle: string): string {
  const pages = labels
    .map(
      (label) => `<section class="label">
  ${label.title ? `<div class="title">${escape(label.title)}</div>` : ''}
  ${barcodeSvg(label.code)}
  <div class="code">${escape(label.code)}</div>
  ${label.subtitle ? `<div class="subtitle">${escape(label.subtitle)}</div>` : ''}
</section>`,
    )
    .join('\n')
  return `<!doctype html>
<html><head><meta charset="utf-8"><title>${escape(documentTitle)}</title>
<style>
  @page { size: 50mm 30mm; margin: 0; }
  * { box-sizing: border-box; }
  body { margin: 0; font-family: Arial, Helvetica, sans-serif; color: #000; }
  .label { width: 50mm; height: 30mm; padding: 1.5mm 2.5mm; display: flex; flex-direction: column;
    justify-content: center; align-items: center; page-break-after: always; overflow: hidden; }
  .label:last-child { page-break-after: auto; }
  .bars { width: 100%; height: 12mm; fill: #000; }
  .title { font-size: 7pt; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; max-width: 100%; }
  .code { font-size: 10pt; font-weight: bold; letter-spacing: 0.5pt; margin-top: 0.5mm; }
  .subtitle { font-size: 6pt; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; max-width: 100%; }
</style></head><body>
${pages}
</body></html>`
}

/** Labels of a reserved range of Horizon IDs (pre-printed, bound at triage). */
export function rangeLabels(first: number, last: number): Label[] {
  const labels: Label[] = []
  for (let number = first; number <= last; number++) {
    labels.push({ code: formatCode('H', number), title: 'Horizon' })
  }
  return labels
}

/** Print labels, one per page. */
export function printLabels(labels: Label[], documentTitle: string): void {
  printDocument(labelsDocument(labels, documentTitle))
}

export { escapeHtml, printDocument }
